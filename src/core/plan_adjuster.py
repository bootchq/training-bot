"""Корректировка плана тренировок при пропусках"""
from datetime import date
from datetime import timedelta
from typing import Any
from typing import Dict

from ..database.db import db
from ..utils.logger import logger


class PlanAdjuster:
    """Динамическая корректировка плана при пропусках"""

    def __init__(self, user_id: int):
        """
        Инициализация

        Args:
            user_id: ID пользователя
        """
        self.user_id = user_id

    def analyze_missed_workouts(self, weeks_back: int = 2) -> Dict[str, Any]:
        """
        Анализ пропущенных тренировок за последние недели

        Args:
            weeks_back: Сколько недель анализировать

        Returns:
            Словарь с информацией о пропусках
        """
        from ..database.db import Training
        from ..database.db import TrainingPlan

        start_date = date.today() - timedelta(weeks=weeks_back)
        end_date = date.today()

        with db.get_session() as session:
            # Получаем все запланированные тренировки за период
            planned = session.query(TrainingPlan).filter(
                TrainingPlan.user_id == self.user_id,
                TrainingPlan.date >= start_date,
                TrainingPlan.date < end_date
            ).all()

            # Получаем фактические тренировки за период
            actual = session.query(Training).filter(
                Training.user_id == self.user_id,
                Training.date >= start_date,
                Training.date < end_date,
                Training.type == 'actual'
            ).all()

            # Считаем пропуски
            actual_dates = {t.date for t in actual}
            missed = []
            missed_long = 0
            missed_intervals = 0

            for plan in planned:
                if plan.date not in actual_dates:
                    missed.append({
                        'date': plan.date,
                        'type': plan.type,
                        'duration_min': plan.duration_min
                    })

                    if plan.type == 'long':
                        missed_long += 1
                    elif plan.type in ['intervals', 'tempo']:
                        missed_intervals += 1

            total_planned = len(planned)
            total_missed = len(missed)
            miss_rate = (total_missed / total_planned * 100) if total_planned > 0 else 0

            return {
                'total_planned': total_planned,
                'total_missed': total_missed,
                'miss_rate': miss_rate,
                'missed_long': missed_long,
                'missed_intervals': missed_intervals,
                'missed_workouts': missed,
                'weeks_analyzed': weeks_back
            }

    def suggest_adjustments(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Предложить корректировки плана на основе анализа

        Args:
            analysis: Результат analyze_missed_workouts

        Returns:
            Словарь с рекомендациями
        """
        miss_rate = analysis['miss_rate']
        missed_long = analysis['missed_long']
        missed_intervals = analysis['missed_intervals']

        suggestions = {
            'severity': 'low',
            'actions': [],
            'volume_adjustment': 1.0,  # Множитель объёма (1.0 = без изменений)
            'message': ''
        }

        # Определяем серьёзность ситуации
        if miss_rate < 20:
            # Минимальные пропуски - всё ок
            suggestions['severity'] = 'low'
            suggestions['message'] = "Отличная дисциплина! Продолжай в том же духе"
            suggestions['actions'].append('continue_as_planned')

        elif miss_rate < 40:
            # Умеренные пропуски
            suggestions['severity'] = 'moderate'
            suggestions['message'] = "Есть пропуски, но ситуация контролируема"

            if missed_long > 0:
                suggestions['actions'].append('add_extra_long')
                suggestions['message'] += ". Добавь дополнительную длинную тренировку"

            if missed_intervals > 1:
                suggestions['actions'].append('reduce_intensity')
                suggestions['volume_adjustment'] = 0.9  # Снизить объём на 10%

        else:
            # Много пропусков - нужна коррекция
            suggestions['severity'] = 'high'
            suggestions['message'] = "Много пропусков. Снижаем объём для безопасности"
            suggestions['actions'].append('reduce_volume')
            suggestions['volume_adjustment'] = 0.75  # Снизить объём на 25%

            if missed_long >= 2:
                suggestions['actions'].append('focus_on_consistency')
                suggestions['message'] += ". Фокус на регулярности, не на объёме"

        return suggestions

    def adjust_future_plan(self, adjustment: Dict[str, Any]) -> int:
        """
        Применить корректировки к будущим тренировкам

        Args:
            adjustment: Результат suggest_adjustments

        Returns:
            Количество изменённых тренировок
        """
        from ..database.db import TrainingPlan

        if 'continue_as_planned' in adjustment['actions']:
            logger.info(f"План user={self.user_id} не требует корректировки")
            return 0

        volume_multiplier = adjustment['volume_adjustment']
        today = date.today()

        with db.get_session() as session:
            # Получаем будущие тренировки (следующие 2 недели)
            future_plans = session.query(TrainingPlan).filter(
                TrainingPlan.user_id == self.user_id,
                TrainingPlan.date >= today,
                TrainingPlan.date < today + timedelta(weeks=2),
                TrainingPlan.is_completed == False
            ).all()

            adjusted_count = 0

            for plan in future_plans:
                if volume_multiplier != 1.0 and plan.duration_min:
                    # Корректируем длительность
                    old_duration = plan.duration_min
                    new_duration = int(plan.duration_min * volume_multiplier)

                    # Минимум 20 минут
                    new_duration = max(20, new_duration)

                    plan.duration_min = new_duration

                    # Пересчитываем дистанцию пропорционально
                    if plan.distance_km and old_duration > 0:
                        plan.distance_km = round(plan.distance_km * (new_duration / old_duration), 1)

                    adjusted_count += 1
                    logger.info(f"Скорректирована тренировка {plan.date}: {old_duration}мин -> {new_duration}мин")

            session.commit()

        logger.info(f"Скорректировано {adjusted_count} тренировок для user={self.user_id}")
        return adjusted_count

    def get_ai_recommendations(self, analysis: Dict[str, Any]) -> str:
        """
        Получить AI-рекомендации на основе анализа

        Args:
            analysis: Результат analyze_missed_workouts

        Returns:
            Текст рекомендаций от AI
        """
        from ..integrations.ai_agent import AIConsultant

        ai = AIConsultant()

        # Получаем цель пользователя
        user_settings = db.get_user_settings(self.user_id)
        goal_info = ""
        if user_settings:
            goal_type = user_settings.get('goal_type', 'fitness')
            goal_distance = user_settings.get('goal_distance_km')
            goal_date = user_settings.get('goal_date')

            if goal_distance and goal_date:
                goal_info = f"Цель: {goal_type}, {goal_distance}км, дата: {goal_date}"

        prompt = f"""Ты тренер по бегу. Дай персонализированные рекомендации по корректировке плана тренировок.

**Ситуация:**
- Проанализировано последние {analysis['weeks_analyzed']} недель
- Запланировано тренировок: {analysis['total_planned']}
- Пропущено: {analysis['total_missed']} ({analysis['miss_rate']:.1f}%)
- Пропущено длинных: {analysis['missed_long']}
- Пропущено интервалов: {analysis['missed_intervals']}

{goal_info}

**Задача:**
Напиши краткие рекомендации (3-4 предложения):
1. Оценка ситуации (позитивно, мотивируй)
2. Что делать дальше
3. Конкретный совет по корректировке плана

Пиши дружелюбно, как личный тренер. Без воды и общих фраз."""

        try:
            recommendations = ai.ask(prompt)
            logger.info(f"AI-рекомендации получены для user={self.user_id}")
            return recommendations
        except Exception as e:
            logger.error(f"Ошибка получения AI-рекомендаций: {e}")
            # Fallback
            if analysis['miss_rate'] < 20:
                return "Отличная дисциплина! Продолжай в том же духе 💪"
            elif analysis['miss_rate'] < 40:
                return "Есть пропуски, но всё исправимо. Фокус на регулярности!"
            else:
                return "Много пропусков. Давай снизим объём и вернём уверенность в себе."

    def check_and_adjust_plan(self, include_ai_recommendations: bool = False) -> Dict[str, Any]:
        """
        Полный цикл: анализ + корректировка

        Args:
            include_ai_recommendations: Добавить AI-рекомендации

        Returns:
            Результат корректировки
        """
        # Анализируем пропуски
        analysis = self.analyze_missed_workouts(weeks_back=2)

        # Получаем рекомендации
        suggestions = self.suggest_adjustments(analysis)

        # Применяем корректировки
        adjusted_count = self.adjust_future_plan(suggestions)

        result = {
            'analysis': analysis,
            'suggestions': suggestions,
            'adjusted_count': adjusted_count
        }

        # Добавляем AI-рекомендации если запрошены
        if include_ai_recommendations:
            result['ai_recommendations'] = self.get_ai_recommendations(analysis)

        return result


def create_plan_adjuster(user_id: int) -> PlanAdjuster:
    """Создать корректор плана"""
    return PlanAdjuster(user_id)
