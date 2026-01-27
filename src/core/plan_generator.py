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
                               time_per_session: int, weeks: int = 4, goal_type: str = 'race',
                               fitness_level: str = None) -> List[Dict[str, Any]]:
        """
        Генерация детального плана тренировок с индивидуальными параметрами

        Args:
            goal_distance: Целевая дистанция забега (км)
            goal_date: Дата забега
            training_days: Список номеров дней недели (1=Пн, ..., 7=Вс)
            time_per_session: Время на одну тренировку (минуты)
            weeks: Количество недель плана
            goal_type: Тип цели (race/trail/fitness)
            fitness_level: Уровень подготовки (beginner/intermediate/advanced), опционально

        Returns:
            Список тренировок с детальным описанием
        """
        trainings = []
        start_date = date.today()

        # Определяем текущий уровень подготовки
        # Приоритет: автоопределение по истории, если нет истории → явный выбор
        from ..core.stats_calculator import StatsCalculator
        calculator = StatsCalculator(self.user_id)
        stats = calculator.get_month_stats()

        if stats['trainings_count'] > 0:
            # Есть история → автоопределение (объективно)
            current_level = self._estimate_current_level()
            logger.info(f"Автоопределён уровень по истории ({stats['trainings_count']} тренировок) user={self.user_id}: {current_level}")
        elif fitness_level:
            # Нет истории + явно указан уровень → используем явный
            current_level = fitness_level
            logger.info(f"Нет истории тренировок, используется явный уровень user={self.user_id}: {current_level}")
        else:
            # Нет истории + не указан уровень → beginner по умолчанию
            current_level = 'beginner'
            logger.info(f"Нет истории и уровня, по умолчанию beginner для user={self.user_id}")

        # Корректируем базовое время в зависимости от уровня
        if current_level == 'beginner':
            time_multiplier = 0.85  # Новички: -15% времени
        elif current_level == 'advanced':
            time_multiplier = 1.15  # Опытные: +15% времени
        else:
            time_multiplier = 1.0  # Средний уровень: без изменений

        adjusted_time = int(time_per_session * time_multiplier)

        # Определяем типы тренировок по дням недели
        workout_types = self._determine_workout_types(training_days, adjusted_time)

        # Периодизация: определяем фазы подготовки
        base_weeks = int(weeks * 0.6)  # 60% - базовый период
        build_weeks = int(weeks * 0.3)  # 30% - развивающий период
        taper_weeks = weeks - base_weeks - build_weeks  # 10% - подводка

        for week_num in range(weeks):
            # Определяем множитель нагрузки в зависимости от периода
            if week_num < base_weeks:
                # Базовый период: постепенный рост от 0.9 до 1.1
                progress = week_num / max(base_weeks - 1, 1)
                week_multiplier = 0.9 + (progress * 0.2)
            elif week_num < base_weeks + build_weeks:
                # Развивающий период: пик нагрузки 1.1-1.2
                progress = (week_num - base_weeks) / max(build_weeks - 1, 1)
                week_multiplier = 1.1 + (progress * 0.1)
            else:
                # Подводка: снижение нагрузки
                weeks_to_race = weeks - week_num
                if weeks_to_race <= 1:
                    # Последняя неделя: сильное снижение (50%)
                    week_multiplier = 0.5
                else:
                    # Предпоследние недели: умеренное снижение (70-80%)
                    week_multiplier = 0.8 - ((taper_weeks - weeks_to_race) * 0.1)

            for day_num in training_days:
                # Преобразуем 1-7 в 0-6 (Python weekday)
                day_offset = (day_num - 1) % 7
                training_date = start_date + timedelta(days=(week_num * 7) + day_offset)

                # Пропускаем прошлые даты и даты после забега
                if training_date < date.today() or training_date > goal_date:
                    continue

                # За 3 дня до забега - только легкие тренировки
                days_to_race = (goal_date - training_date).days
                if days_to_race <= 3 and days_to_race > 0:
                    workout_type = 'recovery'
                else:
                    # Определяем тип тренировки для этого дня
                    workout_type = workout_types.get(day_num, 'easy')

                # Генерируем детальное описание
                workout_details = self._generate_workout_details(
                    workout_type,
                    adjusted_time,
                    week_multiplier,
                    goal_type=goal_type,
                    goal_distance=goal_distance
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

        logger.info(f"Сгенерирован детальный план с периодизацией: {len(trainings)} тренировок на {weeks} недель (база: {base_weeks}н, развитие: {build_weeks}н, подводка: {taper_weeks}н)")
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

    def _generate_workout_details(self, workout_type: str, base_time: int, multiplier: float,
                                  goal_type: str = 'race', goal_distance: int = 21) -> Dict[str, Any]:
        """
        Генерация детального описания тренировки

        Args:
            workout_type: Тип тренировки
            base_time: Базовое время (минуты)
            multiplier: Множитель прогрессии
            goal_type: Тип цели (race/trail/fitness)
            goal_distance: Целевая дистанция (км)

        Returns:
            Словарь с деталями тренировки
        """
        # Применяем прогрессию к общему времени
        total_time = int(base_time * multiplier)

        # Определяем базовый темп в зависимости от типа забега и дистанции
        if goal_type == 'trail':
            # Трейл: медленнее из-за набора высоты
            base_pace = 6.5  # мин/км
            pace_range = "6:00-7:30"
        elif goal_distance >= 42:
            # Марафон и ультра: средний темп
            base_pace = 5.5  # мин/км
            pace_range = "5:00-6:00"
        elif goal_distance >= 21:
            # Полумарафон: чуть быстрее
            base_pace = 5.2  # мин/км
            pace_range = "4:45-5:30"
        else:
            # Короткие дистанции: быстрее
            base_pace = 5.0  # мин/км
            pace_range = "4:30-5:15"

        # Адаптивные разминка/заминка в зависимости от длительности
        if total_time < 40:
            warmup = 10
            cooldown = 5
        elif total_time < 60:
            warmup = 15
            cooldown = 10
        else:
            warmup = 20
            cooldown = 15

        main_time = total_time - warmup - cooldown

        # Валидация: если main_time всё равно отрицательный
        if main_time <= 0:
            main_time = 10  # Минимальная основная часть
            warmup = (total_time - main_time) // 2
            cooldown = total_time - main_time - warmup

        if workout_type == 'intervals':
            # Крейсовые интервалы
            interval_count = max(3, main_time // 12)  # По 12 мин на интервал с отдыхом

            if goal_type == 'trail':
                description = (
                    f"**Интервалы в гору**\n"
                    f"- {warmup} мин z2 (разминка)\n"
                    f"- {interval_count} × подъем 3-5 мин в z3-z4, спуск легко\n"
                    f"- Заминка: {cooldown} мин z1–z2\n"
                    f"- 💡 Найди холм или лестницу для подъемов"
                )
            else:
                description = (
                    f"**Крейсовые интервалы**\n"
                    f"- {warmup} мин z2 (разминка)\n"
                    f"- {interval_count} × 2км в z3, между отрезками отдых 2 мин z1–z2\n"
                    f"- Заминка: {cooldown} мин z1–z2"
                )
            target_zone = 'Z2-Z3'
            distance_km = round(total_time / (base_pace * 0.95), 1)  # Интервалы чуть быстрее базового темпа

        elif workout_type == 'tempo':
            # Темповый бег
            tempo_time = int(main_time * 0.4)  # 40% от основного времени - темп
            recovery_time = main_time - tempo_time

            if goal_type == 'trail':
                description = (
                    f"**Темповый бег по холмам**\n"
                    f"- {warmup} мин z2 (разминка)\n"
                    f"- {tempo_time} мин в z3 (холмистая трасса)\n"
                    f"- {recovery_time} мин z2 (восстановление)\n"
                    f"- Заминка: {cooldown} мин z1–z2\n"
                    f"- 💡 Цель: поддержание усилия на подъемах"
                )
            else:
                description = (
                    f"**Темповый бег непрерывный**\n"
                    f"- {warmup} мин z2 (разминка)\n"
                    f"- {tempo_time} мин непрерывно в z3 (темповый бег)\n"
                    f"- {recovery_time} мин z2 (восстановление)\n"
                    f"- Заминка: {cooldown} мин z1–z2"
                )
            target_zone = 'Z2-Z3'
            distance_km = round(total_time / (base_pace * 0.92), 1)  # Темп чуть быстрее базового

        elif workout_type == 'long':
            # Длинная тренировка
            main_long = main_time

            if goal_type == 'trail':
                # Для трейла акцент на времени в ногах, не на темпе
                description = (
                    f"**Длинная трейловая**\n"
                    f"- {warmup} мин легкая разминка\n"
                    f"- {main_long} мин z2 (поиск холмов и троп)\n"
                    f"- Заминка: {cooldown} мин z1\n"
                    f"- 💡 Цель: время на ногах, не темп. Набор высоты приветствуется"
                )
                distance_km = round(total_time / (base_pace * 1.15), 1)  # Медленнее из-за рельефа
            elif goal_distance >= 42:
                # Марафон: длинные с марафонским темпом
                marathon_pace = min(20, int(main_long * 0.2))  # 20% времени - марафонский темп
                description = (
                    f"**Длинная с марафонским темпом**\n"
                    f"- {warmup} мин z2 (разминка)\n"
                    f"- {main_long - marathon_pace} мин z2 (аэробная база)\n"
                    f"- Последние {marathon_pace} мин: переход в z2–z3 (марафонский темп)\n"
                    f"- Заминка: {cooldown} мин z1–z2\n"
                    f"- 💡 Отработка целевого темпа на усталости"
                )
                distance_km = round(total_time / base_pace, 1)
            else:
                # Полумарафон: длинная в аэробной зоне
                description = (
                    f"**Длинная аэробная**\n"
                    f"- {warmup} мин z2 (разминка)\n"
                    f"- {main_long} мин z2 (комфортный темп)\n"
                    f"- Заминка: {cooldown} мин z1–z2\n"
                    f"- 💡 Держи разговорный темп"
                )
                distance_km = round(total_time / base_pace, 1)
            target_zone = 'Z2'

        elif workout_type == 'recovery':
            # Восстановительная
            description = (
                f"**Восстановительный бег**\n"
                f"- {warmup} мин z1 (легкая разминка)\n"
                f"- {main_time} мин z1–z2 (очень легкий бег)\n"
                f"- Заминка: {cooldown} мин z1\n"
                f"- 💡 Темп медленнее обычного, фокус на восстановлении"
            )
            target_zone = 'Z1-Z2'
            distance_km = round(total_time / (base_pace * 1.2), 1)  # Медленнее на 20%

        else:  # easy
            # Легкий бег
            if goal_type == 'trail':
                description = (
                    f"**Легкий бег по тропам**\n"
                    f"- {warmup} мин z2 (разминка)\n"
                    f"- {main_time} мин z2 (комфортный темп, можно с подъемами)\n"
                    f"- Заминка: {cooldown} мин z1–z2\n"
                    f"- 💡 Адаптация к пересеченной местности"
                )
            else:
                description = (
                    f"**Легкий аэробный бег**\n"
                    f"- {warmup} мин z2 (разминка)\n"
                    f"- {main_time} мин z2 (аэробный бег)\n"
                    f"- Заминка: {cooldown} мин z1–z2\n"
                    f"- 💡 Комфортный разговорный темп"
                )
            target_zone = 'Z2'
            distance_km = round(total_time / base_pace, 1)

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
