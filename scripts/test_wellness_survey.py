"""Тестирование вечернего опроса самочувствия"""
import sys
import os
from pathlib import Path
from datetime import date, timedelta

# Устанавливаем минимальные переменные окружения
os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'dummy')
os.environ.setdefault('GARMIN_EMAIL', 'dummy')
os.environ.setdefault('GARMIN_PASSWORD', 'dummy')

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.db import db, Training
from src.core.wellness_survey import WellnessSurvey
from src.utils.logger import logger


def test_survey_flow():
    """Тест полного flow опроса"""
    logger.info("=" * 50)
    logger.info("🧪 Тест вечернего опроса самочувствия")
    logger.info("=" * 50)

    # Получаем тестового пользователя
    test_telegram_id = 123456789
    user = db.get_or_create_user(test_telegram_id)

    test_date = date(2025, 12, 29)

    # Шаг 1: Создаём тренировку
    logger.info(f"\n1. Создание тренировки на {test_date}")

    with db.get_session() as session:
        # Удаляем старые тестовые данные
        session.query(Training).filter_by(user_id=user.id, date=test_date).delete()

        # Создаём тренировку
        training = Training(
            user_id=user.id,
            date=test_date,
            type='actual',
            distance_km=10.0,
            duration_min=60,
            avg_hr=155
        )
        session.add(training)

    logger.info("✅ Тренировка создана")

    # Шаг 2: Проверка should_send_survey
    logger.info(f"\n2. Проверка необходимости опроса")
    should_send = WellnessSurvey.should_send_survey(user.id, test_date)
    logger.info(f"Результат: {'✅ Да' if should_send else '❌ Нет'}")

    if not should_send:
        logger.error("Тест провален: опрос не должен отправляться")
        return

    # Шаг 3: Создание опроса
    logger.info(f"\n3. Создание опроса")
    text, keyboard = WellnessSurvey.create_survey_message(user.id, test_date)
    logger.info(f"Текст: {text[:50]}...")
    logger.info(f"Кнопок: {len(keyboard.inline_keyboard)} рядов")

    # Шаг 4: Симуляция ответов
    logger.info(f"\n4. Симуляция прохождения опроса")

    # Шаг 4.1: Оценка тренировки (выбираем 8)
    logger.info("Шаг 1: Оценка тренировки = 8")
    result = WellnessSurvey.handle_callback(user.id, "survey_rating_8")
    if result:
        text, keyboard = result
        logger.info(f"✅ {text[:50]}...")
    else:
        logger.error("❌ Ошибка на шаге 1")
        return

    # Шаг 4.2: Самочувствие (выбираем "Отлично")
    logger.info("Шаг 2: Самочувствие = Отлично")
    result = WellnessSurvey.handle_callback(user.id, "survey_wellness_3")
    if result:
        text, keyboard = result
        logger.info(f"✅ {text[:50]}...")
    else:
        logger.error("❌ Ошибка на шаге 2")
        return

    # Шаг 4.3: Боль (нет)
    logger.info("Шаг 3: Боль = Нет")
    result = WellnessSurvey.handle_callback(user.id, "survey_pain_no")
    if result:
        text, keyboard = result
        logger.info(f"✅ {text[:50]}...")
    else:
        logger.error("❌ Ошибка на шаге 3")
        return

    # Шаг 4.4: Сон (отлично)
    logger.info("Шаг 4: Сон = Отлично")
    result = WellnessSurvey.handle_callback(user.id, "survey_sleep_good")
    if result:
        text, keyboard = result
        logger.info(f"✅ Финал: {text[:100]}...")

        if keyboard:
            logger.warning("⚠️  Опрос не завершён (есть клавиатура)")
        else:
            logger.info("✅ Опрос завершён")
    else:
        logger.error("❌ Ошибка на шаге 4")
        return

    # Шаг 5: Проверка сохранения в БД
    logger.info(f"\n5. Проверка сохранения в БД")
    with db.get_session() as session:
        from src.database.db import WellnessSurvey as WellnessSurveyModel

        survey = session.query(WellnessSurveyModel).filter_by(
            user_id=user.id,
            date=test_date
        ).first()

        if survey:
            logger.info(f"✅ Опрос найден в БД:")
            logger.info(f"   - Оценка тренировки: {survey.training_rating}")
            logger.info(f"   - Самочувствие: {survey.wellness_rating}")
            logger.info(f"   - Боль: {survey.pain_reported}")
            logger.info(f"   - Сон: {survey.sleep_quality}")
        else:
            logger.error("❌ Опрос не найден в БД")

    logger.info("\n" + "=" * 50)
    logger.info("✅ Тест завершён успешно")
    logger.info("=" * 50)


def test_survey_not_needed():
    """Тест что опрос не отправляется если нет тренировки"""
    logger.info("\n" + "=" * 50)
    logger.info("🧪 Тест: опрос не нужен (нет тренировки)")
    logger.info("=" * 50)

    test_telegram_id = 123456789
    user = db.get_or_create_user(test_telegram_id)

    # День без тренировки
    no_training_date = date(2025, 12, 30)

    should_send = WellnessSurvey.should_send_survey(user.id, no_training_date)

    if should_send:
        logger.error("❌ Тест провален: опрос не должен отправляться")
    else:
        logger.info("✅ Тест пройден: опрос не требуется")

    logger.info("=" * 50)


if __name__ == "__main__":
    # Создаём таблицы если их нет
    db.create_tables()

    # Тест 1: Полный flow опроса
    test_survey_flow()

    # Тест 2: Опрос не нужен (нет тренировки)
    test_survey_not_needed()
