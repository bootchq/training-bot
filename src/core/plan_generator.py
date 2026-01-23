"""Генератор плана тренировок"""
from datetime import date, timedelta
from typing import List, Dict, Any
from ..database.db import db
from ..utils.logger import logger


class PlanGenerator:
    """Генератор тренировочного плана"""

    def __init__(self, user_id: int):
        """
        Инициализация

        Args:
            user_id: ID пользователя
        """
        self.user_id = user_id

    def generate_base_plan(self, goal_distance: int, goal_date: date, weeks: int = 4) -> List[Dict[str, Any]]:
        """
        Генерация базового плана тренировок

        Args:
            goal_distance: Целевая дистанция забега (км)
            goal_date: Дата забега
            weeks: Количество недель плана

        Returns:
            Список тренировок
        """
        trainings = []
        start_date = date.today()

        # Определяем текущий уровень пользователя
        current_level = self._estimate_current_level()

        # Базовая недельная структура для подготовки к трейлу/марафону
        # Понедельник - отдых, Вторник - база, Среда - темп, Четверг - легкая,
        # Пятница - отдых, Суббота - длинная, Воскресенье - восстановительная

        week_template = [
            {'day': 0, 'type': 'rest', 'description': 'Отдых или растяжка'},  # Понедельник
            {'day': 1, 'type': 'easy', 'duration_min': 45, 'target_zone': 'Z2', 'description': 'Легкий бег в аэробной зоне'},  # Вторник
            {'day': 2, 'type': 'tempo', 'duration_min': 50, 'target_zone': 'Z3-Z4', 'description': 'Темповая тренировка'},  # Среда
            {'day': 3, 'type': 'easy', 'duration_min': 35, 'target_zone': 'Z2', 'description': 'Восстановительный бег'},  # Четверг
            {'day': 4, 'type': 'rest', 'description': 'Отдых'},  # Пятница
            {'day': 5, 'type': 'long', 'duration_min': 120, 'target_zone': 'Z2', 'description': 'Длинная тренировка'},  # Суббота
            {'day': 6, 'type': 'recovery', 'duration_min': 40, 'target_zone': 'Z1-Z2', 'description': 'Легкий восстановительный бег'},  # Воскресенье
        ]

        for week_num in range(weeks):
            # Прогрессия: каждую неделю немного увеличиваем объём
            week_multiplier = 1 + (week_num * 0.1)  # +10% каждую неделю

            for day_template in week_template:
                training_date = start_date + timedelta(days=(week_num * 7) + day_template['day'])

                # Пропускаем даты в прошлом
                if training_date < date.today():
                    continue

                # Не планируем после даты забега
                if training_date > goal_date:
                    continue

                # Отдых - только запись без тренировки
                if day_template['type'] == 'rest':
                    continue

                duration_min = day_template.get('duration_min', 0)
                if duration_min > 0:
                    duration_min = int(duration_min * week_multiplier)

                # Оценка дистанции (5:30 мин/км средний темп для базовых тренировок)
                distance_km = None
                if duration_min > 0:
                    avg_pace_min_per_km = 5.5  # Средний темп
                    distance_km = round(duration_min / avg_pace_min_per_km, 1)

                training = {
                    'date': training_date,
                    'type': day_template['type'],
                    'duration_min': duration_min,
                    'distance_km': distance_km,
                    'target_zone': day_template.get('target_zone'),
                    'description': day_template.get('description', '')
                }

                trainings.append(training)

        logger.info(f"Сгенерирован план на {weeks} недель: {len(trainings)} тренировок")
        return trainings

    def _estimate_current_level(self) -> str:
        """
        Оценка текущего уровня пользователя по статистике

        Returns:
            Уровень: beginner, intermediate, advanced
        """
        from ..core.stats_calculator import StatsCalculator

        calculator = StatsCalculator(self.user_id)
        stats = calculator.get_month_stats()

        if stats['trainings_count'] == 0:
            return 'beginner'

        # Определяем уровень по среднему объёму в неделю
        weeks = 4
        avg_weekly_distance = stats['total_distance'] / weeks

        if avg_weekly_distance < 20:
            return 'beginner'
        elif avg_weekly_distance < 40:
            return 'intermediate'
        else:
            return 'advanced'

    def save_plan_to_db(self, trainings: List[Dict[str, Any]]) -> int:
        """
        Сохранить план тренировок в БД

        Args:
            trainings: Список тренировок

        Returns:
            Количество сохранённых тренировок
        """
        return db.load_training_plan(self.user_id, trainings)


def create_plan_generator(user_id: int) -> PlanGenerator:
    """Создать генератор плана"""
    return PlanGenerator(user_id)
