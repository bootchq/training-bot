"""Модуль вечернего опроса самочувствия"""
from datetime import date, timedelta
from typing import Dict, Any, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ..database.db import db
from ..core.plan_adapter import PlanAdapter
from ..ai.consultant import consultant
from ..utils.logger import logger


class WellnessSurvey:
    """Вечерний опрос самочувствия"""

    # Временное хранилище ответов (в продакшене использовать Redis или БД)
    pending_surveys: Dict[int, Dict[str, Any]] = {}

    @staticmethod
    def should_send_survey(user_id: int, check_date: date) -> bool:
        """
        Проверка: нужно ли отправлять опрос

        Args:
            user_id: ID пользователя
            check_date: Дата для проверки

        Returns:
            True если была тренировка
        """
        training = db.get_training_for_date(user_id, check_date)
        return training is not None

    @staticmethod
    def create_survey_message(user_id: int, training_date: date) -> tuple:
        """
        Создать сообщение с опросом

        Args:
            user_id: ID пользователя
            training_date: Дата тренировки

        Returns:
            (текст, клавиатура)
        """
        # Инициализируем новый опрос
        WellnessSurvey.pending_surveys[user_id] = {
            'date': training_date,
            'step': 1,
            'answers': {}
        }

        text = f"📋 Опрос после тренировки ({training_date.strftime('%d.%m')})\n\n"
        text += "❓ Как оцениваешь тренировку?\n(1 - плохо, 10 - отлично)"

        # Кнопки с оценками 1-10
        keyboard = [
            [InlineKeyboardButton(str(i), callback_data=f"survey_rating_{i}") for i in range(1, 6)],
            [InlineKeyboardButton(str(i), callback_data=f"survey_rating_{i}") for i in range(6, 11)]
        ]

        return text, InlineKeyboardMarkup(keyboard)

    @staticmethod
    def handle_callback(user_id: int, callback_data: str) -> Optional[tuple]:
        """
        Обработка нажатия кнопки

        Args:
            user_id: ID пользователя
            callback_data: Данные callback

        Returns:
            (текст, клавиатура) или None если опрос завершён
        """
        if user_id not in WellnessSurvey.pending_surveys:
            return None

        survey = WellnessSurvey.pending_surveys[user_id]
        step = survey['step']

        # Шаг 1: Оценка тренировки (1-10)
        if step == 1 and callback_data.startswith('survey_rating_'):
            rating = int(callback_data.split('_')[2])
            survey['answers']['training_rating'] = rating
            survey['step'] = 2

            text = "✅ Оценка сохранена\n\n"
            text += "❓ Как себя чувствуешь?"

            keyboard = [
                [
                    InlineKeyboardButton("😫 Усталость", callback_data="survey_wellness_1"),
                    InlineKeyboardButton("😐 Норма", callback_data="survey_wellness_2"),
                    InlineKeyboardButton("😊 Отлично", callback_data="survey_wellness_3")
                ]
            ]

            return text, InlineKeyboardMarkup(keyboard)

        # Шаг 2: Самочувствие (1-3)
        elif step == 2 and callback_data.startswith('survey_wellness_'):
            wellness = int(callback_data.split('_')[2])
            survey['answers']['wellness_rating'] = wellness
            survey['step'] = 3

            text = "✅ Самочувствие сохранено\n\n"
            text += "❓ Есть боль или дискомфорт?"

            keyboard = [
                [
                    InlineKeyboardButton("Да", callback_data="survey_pain_yes"),
                    InlineKeyboardButton("Нет", callback_data="survey_pain_no")
                ]
            ]

            return text, InlineKeyboardMarkup(keyboard)

        # Шаг 3: Боль (да/нет)
        elif step == 3 and callback_data.startswith('survey_pain_'):
            has_pain = callback_data.split('_')[2] == 'yes'
            survey['answers']['pain_reported'] = has_pain

            if has_pain:
                # TODO: можно добавить ввод текста для уточнения места боли
                survey['answers']['pain_location'] = 'Не указано'

            survey['step'] = 4

            text = "✅ Информация о боли сохранена\n\n"
            text += "❓ Как спал прошлой ночью?"

            keyboard = [
                [
                    InlineKeyboardButton("😴 Плохо", callback_data="survey_sleep_bad"),
                    InlineKeyboardButton("😐 Норма", callback_data="survey_sleep_ok"),
                    InlineKeyboardButton("😊 Отлично", callback_data="survey_sleep_good")
                ]
            ]

            return text, InlineKeyboardMarkup(keyboard)

        # Шаг 4: Сон (плохой/норма/отлично)
        elif step == 4 and callback_data.startswith('survey_sleep_'):
            sleep_quality = callback_data.split('_')[2]
            survey['answers']['sleep_quality'] = sleep_quality
            survey['step'] = 5

            # Сохраняем в БД
            WellnessSurvey._save_survey(user_id)

            # Адаптация плана
            changes = WellnessSurvey._adapt_plan_by_wellness(user_id)

            text = "✅ Опрос завершён, спасибо!\n\n"
            text += "📊 Твои ответы сохранены."

            if changes:
                text += f"\n\n📋 План адаптирован:\n"
                for change in changes:
                    text += f"• {change}\n"

            # Удаляем из pending
            del WellnessSurvey.pending_surveys[user_id]

            return text, None

        return None

    @staticmethod
    def _save_survey(user_id: int):
        """Сохранение опроса в БД"""
        if user_id not in WellnessSurvey.pending_surveys:
            return

        survey = WellnessSurvey.pending_surveys[user_id]
        survey_date = survey['date']
        answers = survey['answers']

        db.save_wellness_survey(
            user_id=user_id,
            survey_date=survey_date,
            **answers
        )

        logger.info(f"Опрос сохранён для пользователя {user_id} на {survey_date}")

    @staticmethod
    def _adapt_plan_by_wellness(user_id: int) -> list:
        """Адаптация плана по результатам опроса"""
        if user_id not in WellnessSurvey.pending_surveys:
            return []

        survey = WellnessSurvey.pending_surveys[user_id]
        survey_date = survey['date']
        answers = survey['answers']

        # Получаем оценку тренировки (используем как wellness_rating для адаптации)
        training_rating = answers.get('training_rating', 5)

        # Адаптируем план
        adapter = PlanAdapter(user_id)
        changes = adapter.adapt_on_wellness(survey_date, rating=training_rating)

        return changes

    @staticmethod
    def get_ai_advice_for_survey(user_id: int, survey_date: date) -> Optional[str]:
        """
        Получить AI совет после опроса

        Args:
            user_id: ID пользователя
            survey_date: Дата опроса

        Returns:
            Совет от AI или None
        """
        # Получаем данные опроса из БД
        with db.get_session() as session:
            from ..database.db import WellnessSurvey as WellnessSurveyModel

            survey = session.query(WellnessSurveyModel).filter_by(
                user_id=user_id,
                date=survey_date
            ).first()

            if not survey:
                logger.warning(f"Опрос не найден для пользователя {user_id} на {survey_date}")
                return None

            # Формируем данные для AI
            wellness_data = {
                'training_rating': survey.training_rating,
                'wellness_rating': survey.wellness_rating,
                'pain_reported': survey.pain_reported,
                'pain_location': survey.pain_location,
                'sleep_quality': survey.sleep_quality
            }

        # Получаем совет от AI
        try:
            advice = consultant.get_training_advice(
                user_id=user_id,
                training_date=survey_date,
                wellness_data=wellness_data
            )
            return advice
        except Exception as e:
            logger.error(f"Ошибка получения AI совета: {e}")
            return None


# Экспорт
wellness_survey = WellnessSurvey()
