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

    def generate_detailed_plan(self, goal_distance: int, goal_date: date, training_days: List[int],
                               time_per_session: int, weeks: int = 4) -> List[Dict[str, Any]]:
        """
        Генерация детального плана тренировок с индивидуальными параметрами

        Args:
            goal_distance: Целевая дистанция забега (км)
            goal_date: Дата забега
            training_days: Список номеров дней недели (1=Пн, ..., 7=Вс)
            time_per_session: Время на одну тренировку (минуты)
            weeks: Количество недель плана

        Returns:
            Список тренировок с детальным описанием
        """
        trainings = []
        start_date = date.today()

        # Определяем типы тренировок по дням недели
        workout_types = self._determine_workout_types(training_days, time_per_session)

        for week_num in range(weeks):
            week_multiplier = 1 + (week_num * 0.1)  # Прогрессия +10%

            for day_num in training_days:
                # Преобразуем 1-7 в 0-6 (Python weekday)
                day_offset = (day_num - 1) % 7
                training_date = start_date + timedelta(days=(week_num * 7) + day_offset)

                if training_date < date.today() or training_date > goal_date:
                    continue

                # Определяем тип тренировки для этого дня
                workout_type = workout_types.get(day_num, 'easy')

                # Генерируем детальное описание
                workout_details = self._generate_workout_details(
                    workout_type,
                    time_per_session,
                    week_multiplier
                )

                training = {
                    'date': training_date,
                    'type': workout_type,
                    'duration_min': workout_details['total_time'],
                    'distance_km': workout_details['distance_km'],
                    'target_zone': workout_details['target_zone'],
                    'description': workout_details['description']
                }

                trainings.append(training)

        logger.info(f"Сгенерирован детальный план: {len(trainings)} тренировок")
        return trainings

    def _determine_workout_types(self, training_days: List[int], time_per_session: int) -> Dict[int, str]:
        """
        Определить типы тренировок для каждого дня

        Args:
            training_days: Дни тренировок
            time_per_session: Время на тренировку

        Returns:
            Словарь {день: тип_тренировки}
        """
        workout_types = {}
        num_days = len(training_days)

        # Если 2-3 тренировки в неделю: легкая + длинная (+ интервалы)
        if num_days == 2:
            workout_types[training_days[0]] = 'easy'
            workout_types[training_days[1]] = 'long'
        elif num_days == 3:
            workout_types[training_days[0]] = 'intervals'
            workout_types[training_days[1]] = 'easy'
            workout_types[training_days[2]] = 'long'
        # Если 4-5 тренировок: интервалы + темп + легкая + длинная (+ восстановительная)
        elif num_days == 4:
            workout_types[training_days[0]] = 'intervals'
            workout_types[training_days[1]] = 'tempo'
            workout_types[training_days[2]] = 'easy'
            workout_types[training_days[3]] = 'long'
        else:  # 5+ тренировок
            workout_types[training_days[0]] = 'intervals'
            workout_types[training_days[1]] = 'easy'
            workout_types[training_days[2]] = 'tempo'
            workout_types[training_days[3]] = 'easy'
            workout_types[training_days[4]] = 'long'
            # Остальные дни - восстановительные
            for i in range(5, num_days):
                workout_types[training_days[i]] = 'recovery'

        return workout_types

    def _generate_workout_details(self, workout_type: str, base_time: int, multiplier: float) -> Dict[str, Any]:
        """
        Генерация детального описания тренировки

        Args:
            workout_type: Тип тренировки
            base_time: Базовое время (минуты)
            multiplier: Множитель прогрессии

        Returns:
            Словарь с деталями тренировки
        """
        warmup = 20  # Разминка всегда 20 мин
        cooldown = 15  # Заминка всегда 15 мин
        main_time = base_time - warmup - cooldown

        if workout_type == 'intervals':
            # Крейсовые интервалы
            interval_count = max(3, main_time // 12)  # По 12 мин на интервал с отдыхом
            description = (
                f"**Крейсовые интервалы**\n"
                f"- {warmup} мин z2 (разминка)\n"
                f"- {interval_count} × 2км в z3, между отрезками отдых 2 мин z1–z2\n"
                f"- Заминка: {cooldown} мин z1–z2"
            )
            target_zone = 'Z2-Z3'
            distance_km = round((base_time * multiplier) / 5.0, 1)  # 5 мин/км средний темп

        elif workout_type == 'tempo':
            # Темповый бег
            tempo_time = int(main_time * 0.4)  # 40% от основного времени - темп
            recovery_time = main_time - tempo_time
            description = (
                f"**Темповый бег непрерывный**\n"
                f"- {warmup} мин z2 (разминка)\n"
                f"- {tempo_time} мин непрерывно в z3 (темповый бег)\n"
                f"- {recovery_time} мин z2 (восстановление)\n"
                f"- Заминка: {cooldown} мин z1–z2"
            )
            target_zone = 'Z2-Z3'
            distance_km = round((base_time * multiplier) / 5.2, 1)  # 5:12 мин/км темп

        elif workout_type == 'long':
            # Длинная тренировка
            main_long = main_time
            marathon_pace = 15  # Последние 15 мин - марафонский темп
            description = (
                f"**Длинная с марафонским темпом**\n"
                f"- {warmup} мин z2 (разминка)\n"
                f"- {main_long - marathon_pace} мин z2 (основная часть)\n"
                f"- Последние {marathon_pace} мин: переход в z2–z3 (марафонский темп)\n"
                f"- Заминка: {cooldown} мин z1–z2"
            )
            target_zone = 'Z2'
            distance_km = round((base_time * multiplier) / 5.5, 1)  # 5:30 мин/км

        elif workout_type == 'recovery':
            # Восстановительная
            description = (
                f"**Восстановительный бег**\n"
                f"- {warmup} мин z1 (легкая разминка)\n"
                f"- {main_time} мин z1–z2 (легкий бег)\n"
                f"- Заминка: {cooldown} мин z1"
            )
            target_zone = 'Z1-Z2'
            distance_km = round((base_time * multiplier) / 6.0, 1)  # 6 мин/км медленный

        else:  # easy
            # Легкий бег
            description = (
                f"**Легкий аэробный бег**\n"
                f"- {warmup} мин z2 (разминка)\n"
                f"- {main_time} мин z2 (аэробный бег)\n"
                f"- Заминка: {cooldown} мин z1–z2"
            )
            target_zone = 'Z2'
            distance_km = round((base_time * multiplier) / 5.5, 1)  # 5:30 мин/км

        total_time = int(base_time * multiplier)

        return {
            'description': f"{description}\n- **~{total_time} минут (~{distance_km}км)**",
            'total_time': total_time,
            'distance_km': distance_km,
            'target_zone': target_zone
        }

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
