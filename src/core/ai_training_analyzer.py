"""AI-анализ тренировок с рекомендациями"""
from typing import Optional
from ..database.db import Training
from ..integrations.ai_consultant import AIConsultant
from ..utils.logger import logger


class TrainingAnalyzer:
    """Анализатор тренировок с использованием AI"""

    def __init__(self):
        """Инициализация"""
        self.ai_consultant = AIConsultant()

    def analyze_training(self, training: Training, user_goal: Optional[dict] = None) -> str:
        """
        Анализ тренировки и генерация рекомендаций

        Args:
            training: Объект тренировки
            user_goal: Цель пользователя (опционально)

        Returns:
            Текст анализа и рекомендаций
        """
        # Формируем данные тренировки для AI
        training_data = self._format_training_data(training)

        # Формируем промпт
        prompt = self._build_analysis_prompt(training_data, user_goal)

        try:
            # Получаем анализ от AI
            analysis = self.ai_consultant.ask(prompt)
            logger.info(f"✅ AI-анализ тренировки получен для training_id={training.id}")
            return analysis
        except Exception as e:
            logger.error(f"❌ Ошибка AI-анализа тренировки: {e}")
            return self._get_fallback_analysis(training)

    def _format_training_data(self, training: Training) -> dict:
        """Форматирование данных тренировки"""
        data = {
            'date': training.date.strftime('%d.%m.%Y'),
            'distance_km': training.distance_km,
            'duration_min': training.duration_min,
            'avg_pace': training.avg_pace,
            'avg_hr': training.avg_hr,
            'max_hr': training.max_hr,
            'elevation_m': training.elevation_m,
            'hr_zones': training.hr_zones
        }

        # Вычисляем дополнительные метрики
        if training.duration_min and training.distance_km:
            data['pace_min_km'] = training.duration_min / training.distance_km

        # Определяем тип тренировки по зонам пульса
        if training.hr_zones:
            data['workout_type'] = self._determine_workout_type(training.hr_zones)

        return data

    def _determine_workout_type(self, hr_zones: dict) -> str:
        """Определить тип тренировки по зонам пульса"""
        if not hr_zones:
            return "неизвестно"

        total_time = sum(hr_zones.values())
        if total_time == 0:
            return "неизвестно"

        # Процент времени в каждой зоне
        z1_z2_percent = (hr_zones.get('z1', 0) + hr_zones.get('z2', 0)) / total_time * 100
        z3_z4_percent = (hr_zones.get('z3', 0) + hr_zones.get('z4', 0)) / total_time * 100
        z5_percent = hr_zones.get('z5', 0) / total_time * 100

        if z5_percent > 10:
            return "анаэробная (спринт)"
        elif z3_z4_percent > 50:
            return "пороговая/интенсивная"
        elif z1_z2_percent > 70:
            return "аэробная (база)"
        else:
            return "смешанная"

    def _build_analysis_prompt(self, training_data: dict, user_goal: Optional[dict]) -> str:
        """Построить промпт для AI-анализа"""
        prompt = f"""Ты тренер по бегу. Проанализируй тренировку и дай краткие рекомендации.

**Данные тренировки:**
- Дата: {training_data['date']}
- Дистанция: {training_data.get('distance_km', 'н/д'):.2f} км
- Время: {training_data.get('duration_min', 0)} мин
- Темп: {training_data.get('avg_pace', 'н/д')}
- Средний пульс: {training_data.get('avg_hr', 'н/д')} bpm
- Макс пульс: {training_data.get('max_hr', 'н/д')} bpm
- Набор высоты: {training_data.get('elevation_m', 0)} м
- Тип тренировки: {training_data.get('workout_type', 'неизвестно')}
"""

        if user_goal:
            goal_text = f"""
**Цель пользователя:**
- Тип: {user_goal.get('goal_type', 'н/д')}
- Дистанция: {user_goal.get('goal_distance_km', 'н/д')} км
"""
            prompt += goal_text

        prompt += """
Напиши краткий анализ (3-4 предложения):
1. Что получилось хорошо
2. На что обратить внимание
3. Одна конкретная рекомендация для следующей тренировки

Пиши дружелюбно, мотивируй, будь конкретным. Без воды и общих фраз.
"""

        return prompt

    def _get_fallback_analysis(self, training: Training) -> str:
        """Резервный анализ при ошибке AI"""
        if not training.distance_km:
            return "✅ Тренировка записана! Продолжай в том же духе."

        pace_text = f", темп {training.avg_pace}" if training.avg_pace else ""
        hr_text = f", средний пульс {training.avg_hr} bpm" if training.avg_hr else ""

        return (
            f"✅ Отличная тренировка!\n\n"
            f"📏 {training.distance_km:.2f} км{pace_text}{hr_text}\n\n"
            f"Продолжай регулярные тренировки — прогресс не заставит себя ждать! 💪"
        )


# Глобальный экземпляр
training_analyzer = TrainingAnalyzer()


def get_training_analyzer() -> TrainingAnalyzer:
    """Получить экземпляр анализатора"""
    return training_analyzer
