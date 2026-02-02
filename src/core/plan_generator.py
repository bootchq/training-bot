"""
Генератор плана тренировок — гибридная методология

=== ИСТОЧНИКИ ===
- Jack Daniels "Running Formula" (2021): VDOT калькулятор, 5 зон темпов
- Matt Fitzgerald "80/20 Running": поляризованное распределение
- Joe Friel: зоны пульса по LTHR
- Pete Pfitzinger "Advanced Marathoning" (2025): периодизация
- Norwegian Model (2025): двойной порог, контроль лактата
- Kenyan Methods: высокий объём, низкая интенсивность

=== КЛЮЧЕВЫЕ ПРИНЦИПЫ ===

1. ПЕРСОНАЛИЗАЦИЯ ТЕМПОВ (Jack Daniels VDOT):
   - VDOT рассчитывается по лучшему результату на 5k/10k/half/marathon
   - 5 зон: E (Easy), M (Marathon), T (Threshold), I (Interval), R (Repetition)
   - Таблица VDOT 30-70 с интерполяцией

2. ПЕРСОНАЛИЗАЦИЯ ПУЛЬСА (Joe Friel LTHR):
   - Зоны относительно лактатного порога (LTHR)
   - Z1: <85% LTHR, Z2: 85-89%, Z3: 90-94%, Z4: 95-99%, Z5: 100%+

3. РАСПРЕДЕЛЕНИЕ 80/20 (Matt Fitzgerald):
   - 80% тренировок — лёгкие (Z1-Z2)
   - 20% тренировок — интенсивные (Z4-Z5)
   - Минимум времени в Z3 (пороговая зона)
   - Научная база: +11.3 мин на марафоне vs pyramidal (Nature, 2025)

4. ПЕРИОДИЗАЦИЯ (Pfitzinger/Canova):
   - BASE (60%): развитие аэробной базы, VO2max интервалы
   - BUILD (30%): специфичность, ПАНО работа, mix интервалов
   - PEAK (10%): короткие ускорения, свежесть, нервная система

5. РАЗГРУЗОЧНЫЕ НЕДЕЛИ:
   - Каждая 4-я неделя: -25% объёма
   - Правило "3 вверх, 1 вниз"

6. РОТАЦИЯ ИНТЕРВАЛОВ:
   - 10 форматов в workout_templates.py
   - Не повторять тот же формат 2 недели подряд
   - Выбор по периоду: BASE → VO2max, BUILD → mix, PEAK → короткие

7. ВАЛИДАЦИЯ ОТДЫХА:
   - Минимум 2 дня отдыха в неделю
   - После длинной (Вс) — понедельник отдых
   - Не более 3 тренировочных дней подряд

8. ТРЕЙЛОВАЯ СПЕЦИФИКА:
   - Горки вместо обычных интервалов (30% шанс)
   - Целевой набор высоты = 50-80% от соревновательного
   - Время на ногах важнее темпа
"""
from datetime import date
from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import Dict
from typing import List

import random

from ..database.db import db
from ..utils.logger import logger
from .hr_zones import format_hr_range_for_workout
from .hr_zones import get_workout_hr_description
from .vdot_calculator import get_training_paces
from .vdot_calculator import get_training_paces_seconds
from .workout_templates import (
    INTERVAL_TEMPLATES,
    HILL_TEMPLATES,
    STRENGTH_TEMPLATES,
    TrainingPeriod,
    IntervalFocus,
    get_suitable_intervals,
    format_interval_description,
    format_strength_description,
    format_hill_description,
)


class PlanGenerator:
    """Генератор тренировочного плана по Jack Daniels"""

    def __init__(self, user_id: int):
        """
        Инициализация

        Args:
            user_id: ID пользователя
        """
        self.user_id = user_id
        self.user_settings = db.get_user_settings(user_id)
        self.vdot = self.user_settings.get('vdot') if self.user_settings else None
        self.lthr = self.user_settings.get('lthr') if self.user_settings else None
        self.paces = get_training_paces(self.vdot) if self.vdot else None
        # История использованных шаблонов интервалов (для ротации)
        self.recent_interval_templates: List[str] = []

    def generate_detailed_plan(self, goal_distance: int, goal_date: date, training_days: List[int],
                               time_per_session: int, weeks: int = 4, goal_type: str = 'race',
                               fitness_level: str = None) -> List[Dict[str, Any]]:
        """
        Генерация детального плана тренировок с персонализацией

        Args:
            goal_distance: Целевая дистанция забега (км)
            goal_date: Дата забега
            training_days: Список номеров дней недели (1=Пн, ..., 7=Вс)
            time_per_session: Время на одну тренировку (минуты)
            weeks: Количество недель плана
            goal_type: Тип цели (race/trail/fitness)
            fitness_level: Уровень подготовки (beginner/intermediate/advanced)

        Returns:
            Список тренировок с детальным описанием
        """
        trainings = []

        # Cutoff 20:00: после 20:00 сегодняшний день не включаем в план
        now = datetime.now()
        if now.hour >= 20:
            # После 20:00 — "сегодня" для плана = завтра
            effective_today = date.today() + timedelta(days=1)
        else:
            effective_today = date.today()

        # Для каждого дня недели находим ближайшую дату >= effective_today
        # day_num: 1=Пн, 7=Вс → Python weekday: 0=Пн, 6=Вс
        def next_weekday(from_date: date, day_num: int) -> date:
            """Найти ближайшую дату с этим днём недели"""
            target_weekday = day_num - 1  # Конвертируем в Python формат
            days_ahead = target_weekday - from_date.weekday()
            if days_ahead < 0:  # Уже прошёл на этой неделе
                days_ahead += 7
            return from_date + timedelta(days=days_ahead)

        # Определяем уровень подготовки
        current_level = self._get_fitness_level(fitness_level)

        # Корректируем время под уровень
        time_multiplier = self._get_level_multiplier(current_level)
        adjusted_time = int(time_per_session * time_multiplier)

        # Валидация дней отдыха (минимум 2 дня, не более 3 подряд)
        training_days = self._validate_rest_days(training_days)

        # Определяем типы тренировок по правилу 80/20
        workout_schedule = self._create_80_20_schedule(training_days, weeks)

        for week_num in range(weeks):
            # Разгрузочная неделя каждая 4-я
            is_recovery_week = (week_num + 1) % 4 == 0 and week_num > 0

            # Множитель нагрузки
            week_multiplier = self._get_week_multiplier(week_num, weeks, is_recovery_week)

            for day_num in training_days:
                # Находим ближайшую дату этого дня недели + смещение на нужную неделю
                base_date = next_weekday(effective_today, day_num)
                training_date = base_date + timedelta(days=week_num * 7)

                # Пропускаем даты после цели
                if training_date > goal_date:
                    continue

                # Тип тренировки из расписания 80/20
                workout_type = workout_schedule.get((week_num, day_num), 'easy')

                # За 3 дня до забега — только восстановление
                days_to_race = (goal_date - training_date).days
                if 0 < days_to_race <= 3:
                    workout_type = 'recovery'

                # В разгрузочную неделю — без интервалов
                if is_recovery_week and workout_type in ['intervals', 'vo2max']:
                    workout_type = 'easy'

                # Определяем выходной (Сб=5, Вс=6 в weekday())
                is_weekend = training_date.weekday() >= 5

                # === ПРАВИЛА ДЛИТЕЛЬНОСТИ ===
                # Беговые тренировки: минимум 60 мин, обычно 60-90 мин
                # Длинный бег: 120-180 мин в зависимости от уровня и недели
                # Восстановительный: 30-45 мин

                if workout_type == 'long':
                    # Длинный бег: 120-180 мин
                    # Базовые недели: 120 мин, развивающие: до 180 мин
                    if is_recovery_week:
                        session_time = 90  # Разгрузочная неделя
                    elif week_multiplier >= 1.1:
                        session_time = 150  # Развивающий период
                    else:
                        session_time = 120  # Базовый период
                elif workout_type == 'recovery':
                    # Восстановительный: 30-45 мин
                    session_time = 40
                else:
                    # Беговые тренировки (easy, intervals, tempo): 60-90 мин
                    # Минимум 60 мин — базовое правило
                    session_time = 60 if current_level == 'beginner' else 75

                # Генерируем детали тренировки
                workout_details = self._generate_workout_details(
                    workout_type=workout_type,
                    base_time=session_time,
                    multiplier=week_multiplier,
                    goal_type=goal_type,
                    goal_distance=goal_distance,
                    is_recovery_week=is_recovery_week,
                    week_num=week_num,
                    total_weeks=weeks
                )

                training = {
                    'date': training_date,
                    'type': workout_type,
                    'duration_min': workout_details['total_time'],
                    'distance_km': workout_details['distance_km'],
                    'target_zone': workout_details['target_zone'],
                    'description': workout_details['description'],
                    'goal': self._get_workout_goal(workout_type),
                    'week_num': week_num + 1,
                    'is_recovery_week': is_recovery_week
                }

                trainings.append(training)

        logger.info(f"Сгенерирован план: {len(trainings)} тренировок, VDOT={self.vdot}, LTHR={self.lthr}")
        return trainings

    def _get_fitness_level(self, explicit_level: str = None) -> str:
        """Определить уровень подготовки"""
        from ..core.stats_calculator import StatsCalculator

        calculator = StatsCalculator(self.user_id)
        stats = calculator.get_month_stats()

        if stats['trainings_count'] > 0:
            # Автоопределение по истории
            avg_weekly = stats['total_distance'] / 4
            if avg_weekly < 20:
                return 'beginner'
            elif avg_weekly < 40:
                return 'intermediate'
            else:
                return 'advanced'

        return explicit_level or 'beginner'

    def _get_level_multiplier(self, level: str) -> float:
        """Множитель времени по уровню"""
        multipliers = {
            'beginner': 0.85,
            'intermediate': 1.0,
            'advanced': 1.15
        }
        return multipliers.get(level, 1.0)

    def _get_workout_goal(self, workout_type: str) -> str:
        """Получить цель тренировки для отображения пользователю"""
        goals = {
            'intervals': "Цель: Повышение VO2max — рост выносливости",
            'vo2max': "Цель: Повышение VO2max — рост выносливости",
            'tempo': "Цель: Развитие порогового темпа — увеличение скорости",
            'threshold': "Цель: Развитие порогового темпа — увеличение скорости",
            'long': "Цель: Развитие аэробной базы — выносливость на длинных дистанциях",
            'easy': "Цель: Аэробная база и восстановление — подготовка к нагрузкам",
            'recovery': "Цель: Активное восстановление — улучшение кровообращения"
        }
        return goals.get(workout_type, "Цель: Общая физическая подготовка")

    def _get_week_multiplier(self, week_num: int, total_weeks: int, is_recovery_week: bool) -> float:
        """
        Множитель нагрузки для недели

        Периодизация: 3 недели вверх, 1 неделя вниз (разгрузочная)
        """
        if is_recovery_week:
            return 0.75  # -25% в разгрузочную неделю

        # Периоды подготовки
        base_weeks = int(total_weeks * 0.6)
        build_weeks = int(total_weeks * 0.3)

        if week_num < base_weeks:
            # Базовый период: 0.9 → 1.1
            progress = week_num / max(base_weeks - 1, 1)
            return 0.9 + (progress * 0.2)
        elif week_num < base_weeks + build_weeks:
            # Развивающий период: 1.1 → 1.2
            progress = (week_num - base_weeks) / max(build_weeks - 1, 1)
            return 1.1 + (progress * 0.1)
        else:
            # Подводка: снижение
            weeks_to_race = total_weeks - week_num
            if weeks_to_race <= 1:
                return 0.5
            return 0.7

    def _create_80_20_schedule(self, training_days: List[int], weeks: int) -> Dict[tuple, str]:
        """
        Создать расписание по правилу 80/20

        80% тренировок — лёгкие (easy, long, recovery)
        20% тренировок — интенсивные (intervals, tempo, threshold)
        """
        schedule = {}
        num_days = len(training_days)

        # Распределение типов тренировок по количеству дней
        # Ключевые тренировки: максимум 2 в неделю
        if num_days <= 2:
            # 2 дня: easy + long
            types = ['easy', 'long']
        elif num_days == 3:
            # 3 дня: intervals + easy + long (1 интенсивная из 3 = 33%, но длинная это тоже база)
            types = ['intervals', 'easy', 'long']
        elif num_days == 4:
            # 4 дня: intervals + easy + tempo + long (2 интенсивные из 4 = 50% -> нужно скорректировать)
            # По 80/20: 80% = 3.2 лёгких, 20% = 0.8 интенсивных
            # Компромисс: 1 интенсивная + 3 лёгких, но длинная = база
            types = ['intervals', 'easy', 'easy', 'long']
        elif num_days == 5:
            # 5 дней: 80% = 4 лёгких, 20% = 1 интенсивная
            types = ['intervals', 'easy', 'easy', 'easy', 'long']
        else:
            # 6+ дней: добавляем темповую как вторую ключевую
            types = ['intervals', 'easy', 'tempo', 'easy', 'long', 'recovery']
            types = types[:num_days]

        for week_num in range(weeks):
            for i, day_num in enumerate(training_days):
                workout_type = types[i] if i < len(types) else 'easy'
                schedule[(week_num, day_num)] = workout_type

        return schedule

    def _get_training_period(self, week_num: int, total_weeks: int) -> TrainingPeriod:
        """
        Определить период подготовки по номеру недели

        Периодизация:
        - Базовый: первые 60% (акцент на VO2max)
        - Развивающий: следующие 30% (mix скорости и ПАНО)
        - Подводка: последние 10% (короткие, быстрые)
        """
        progress = week_num / max(total_weeks - 1, 1)

        if progress < 0.6:
            return TrainingPeriod.BASE
        elif progress < 0.9:
            return TrainingPeriod.BUILD
        else:
            return TrainingPeriod.PEAK

    def _select_interval_template(self, week_num: int, total_weeks: int,
                                   goal_distance: int, goal_type: str) -> Dict:
        """
        Выбор формата интервалов с ротацией

        Принципы:
        1. Не повторять тот же формат 2 недели подряд
        2. В базовом периоде — больше VO2max (длинные интервалы)
        3. В развивающем — mix скорости и ПАНО
        4. Перед забегом — короткие ускорения для нервной системы
        5. Для трейла — добавляем горки
        """
        period = self._get_training_period(week_num, total_weeks)

        # Получаем подходящие шаблоны с учётом недавно использованных
        suitable_keys = get_suitable_intervals(period, self.recent_interval_templates)

        # Для длинных забегов (>21км) в развивающем периоде добавляем ПАНО
        if goal_distance >= 21 and period == TrainingPeriod.BUILD:
            if 'threshold_2k' not in suitable_keys:
                suitable_keys.append('threshold_2k')

        # Для трейла добавляем возможность горок
        if goal_type == 'trail' and period != TrainingPeriod.PEAK:
            # 30% шанс на горки вместо обычных интервалов
            if random.random() < 0.3:
                return {'type': 'hills', 'template_key': 'medium_hills'}

        # Случайный выбор из подходящих
        if suitable_keys:
            selected_key = random.choice(suitable_keys)
        else:
            selected_key = 'vo2max_5min'  # fallback

        # Запоминаем использованный шаблон
        self.recent_interval_templates.append(selected_key)
        if len(self.recent_interval_templates) > 4:
            self.recent_interval_templates.pop(0)

        template = INTERVAL_TEMPLATES.get(selected_key, INTERVAL_TEMPLATES['vo2max_5min'])
        return {'type': 'intervals', 'template_key': selected_key, 'template': template}

    def _validate_rest_days(self, training_days: List[int]) -> List[int]:
        """
        Проверка и корректировка дней отдыха

        Правила:
        1. Минимум 2 дня отдыха в неделю
        2. После длинной (воскресенье) — понедельник отдых
        3. Не более 3 тренировочных дней подряд
        """
        all_days = set(range(1, 8))  # 1-7 (Пн-Вс)
        rest_days = all_days - set(training_days)

        # Правило 1: минимум 2 дня отдыха
        if len(rest_days) < 2:
            # Убираем лишние дни (приоритет: понедельник, пятница)
            to_remove = []
            if 1 in training_days:  # Понедельник
                to_remove.append(1)
            if 5 in training_days and len(to_remove) < 2 - len(rest_days):
                to_remove.append(5)

            training_days = [d for d in training_days if d not in to_remove]

        # Правило 2: после длинной (обычно Вс=7) — Пн=1 отдых
        if 7 in training_days and 1 in training_days:
            training_days = [d for d in training_days if d != 1]

        # Правило 3: не более 3 подряд
        training_days = sorted(training_days)
        result = []
        consecutive = 0
        prev_day = 0

        for day in training_days:
            if prev_day and day == prev_day + 1:
                consecutive += 1
            else:
                consecutive = 1

            if consecutive <= 3:
                result.append(day)
            prev_day = day

        return result

    def _generate_strength(self, strength_type: str = 'sbu_drills') -> Dict:
        """
        Генерация силовой тренировки

        Args:
            strength_type: 'gym_ofp' | 'sbu_drills' | 'outdoor_ofp' | 'core_stability'
        """
        template = STRENGTH_TEMPLATES.get(strength_type, STRENGTH_TEMPLATES['sbu_drills'])
        description = format_strength_description(strength_type)

        return {
            'description': description,
            'target_zone': 'Strength',
            'duration_min': template['duration_min'],
            'type': 'strength',
            'distance_km': 0,
        }

    def _generate_hills(self, main_time: int, warmup: int, cooldown: int,
                        hill_type: str, pace_info: str, hr_info: str) -> Dict:
        """
        Генерация горной тренировки

        Args:
            hill_type: Ключ из HILL_TEMPLATES
        """
        template = HILL_TEMPLATES.get(hill_type, HILL_TEMPLATES['medium_hills'])

        # Рассчитываем параметры
        if 'work_distance_m' in template:
            distance_range = template['work_distance_m']
            distance = random.randint(distance_range[0], distance_range[1])
            distance_str = f"{distance}м"
        else:
            time_range = template.get('work_time_min', (3, 5))
            time_val = random.randint(time_range[0], time_range[1])
            distance_str = f"{time_val} мин"

        gradient_range = template.get('gradient_percent', (6, 10))
        gradient = random.randint(gradient_range[0], gradient_range[1])

        reps_range = template['repetitions_range']
        # Подбираем кол-во повторов под доступное время
        max_reps = min(reps_range[1], int(main_time / 5))  # ~5 мин на повтор
        reps = max(reps_range[0], max_reps)

        description = f"""**{template['name']}**

🏃 **Разминка:** {warmup} мин лёгкий бег

{format_hill_description(hill_type, reps, distance_str, gradient)}

🧘 **Заминка:** {cooldown} мин лёгкий бег

{pace_info}
💓 Пульс на подъёме: Z4-Z5
"""
        return {
            'description': description,
            'target_zone': 'Z4-Z5',
        }

    def _generate_workout_details(self, workout_type: str, base_time: int, multiplier: float,
                                  goal_type: str = 'race', goal_distance: int = 21,
                                  is_recovery_week: bool = False,
                                  week_num: int = 0, total_weeks: int = 8) -> Dict[str, Any]:
        """
        Генерация детального описания тренировки с персонализацией

        Args:
            week_num: Номер текущей недели (для выбора шаблона интервалов)
            total_weeks: Общее количество недель (для определения периода)
        """
        total_time = int(base_time * multiplier)

        # Темпы по VDOT (если есть)
        pace_info = self._get_pace_info(workout_type)

        # Зона пульса по LTHR (если есть)
        hr_info = self._get_hr_info(workout_type)

        # Разминка/заминка
        warmup, cooldown = self._get_warmup_cooldown(total_time)
        main_time = max(10, total_time - warmup - cooldown)

        # Базовый темп для расчёта дистанции
        base_pace = self._get_base_pace(goal_type, goal_distance)

        if workout_type == 'intervals' or workout_type == 'vo2max':
            details = self._generate_intervals(
                main_time, warmup, cooldown, goal_type, pace_info, hr_info,
                week_num=week_num, total_weeks=total_weeks, goal_distance=goal_distance
            )
        elif workout_type == 'tempo' or workout_type == 'threshold':
            details = self._generate_tempo(main_time, warmup, cooldown, goal_type, pace_info, hr_info)
        elif workout_type == 'long':
            details = self._generate_long_run(main_time, warmup, cooldown, goal_type, goal_distance, pace_info, hr_info)
        elif workout_type == 'recovery':
            details = self._generate_recovery(total_time, pace_info, hr_info)
        elif workout_type == 'strength':
            details = self._generate_strength('sbu_drills')
        else:  # easy
            details = self._generate_easy(main_time, warmup, cooldown, goal_type, pace_info, hr_info)

        # Расчёт дистанции
        details['distance_km'] = self._calculate_distance(total_time, workout_type, base_pace)
        details['total_time'] = total_time

        return details

    def _get_pace_info(self, workout_type: str) -> str:
        """Получить информацию о темпе по VDOT"""
        if not self.paces:
            return ""

        pace_mapping = {
            'easy': f"Темп: {self.paces['easy_range']}/км",
            'recovery': f"Темп: медленнее {self.paces['easy']}/км",
            'long': f"Темп: {self.paces['easy_range']}/км",
            'tempo': f"Темп: {self.paces['threshold']}/км",
            'threshold': f"Темп: {self.paces['threshold']}/км",
            'intervals': f"Темп интервалов: {self.paces['interval']}/км",
            'vo2max': f"Темп интервалов: {self.paces['interval']}/км",
        }
        return pace_mapping.get(workout_type, "")

    def _get_hr_info(self, workout_type: str) -> str:
        """Получить информацию о пульсе по LTHR"""
        if self.lthr:
            return format_hr_range_for_workout(workout_type, self.lthr)
        return get_workout_hr_description(workout_type, None)

    def _get_warmup_cooldown(self, total_time: int) -> tuple:
        """Расчёт разминки и заминки"""
        if total_time < 40:
            return 8, 5
        elif total_time < 60:
            return 12, 8
        else:
            return 15, 10

    def _get_base_pace(self, goal_type: str, goal_distance: int) -> float:
        """Базовый темп в мин/км для расчёта дистанции"""
        if self.paces:
            # Используем Easy темп из VDOT
            paces_sec = get_training_paces_seconds(self.vdot)
            return paces_sec['easy'] / 60
        elif goal_type == 'trail':
            return 6.5
        elif goal_distance >= 42:
            return 5.5
        elif goal_distance >= 21:
            return 5.2
        else:
            return 5.0

    def _calculate_distance(self, total_time: int, workout_type: str, base_pace: float) -> float:
        """Расчёт дистанции"""
        pace_multipliers = {
            'recovery': 1.2,
            'easy': 1.0,
            'long': 1.0,
            'tempo': 0.92,
            'threshold': 0.92,
            'intervals': 0.95,
            'vo2max': 0.95,
        }
        multiplier = pace_multipliers.get(workout_type, 1.0)
        return round(total_time / (base_pace * multiplier), 1)

    def _generate_intervals(self, main_time: int, warmup: int, cooldown: int,
                           goal_type: str, pace_info: str, hr_info: str,
                           week_num: int = 0, total_weeks: int = 8,
                           goal_distance: int = 21) -> Dict:
        """
        Генерация интервальной тренировки с разнообразием

        Использует шаблоны из workout_templates.py с ротацией по неделям.
        """
        # Выбираем шаблон
        selection = self._select_interval_template(week_num, total_weeks, goal_distance, goal_type)

        # Если выбраны горки (для трейла)
        if selection['type'] == 'hills':
            return self._generate_hills(main_time, warmup, cooldown,
                                        selection['template_key'], pace_info, hr_info)

        template = selection['template']
        template_key = selection['template_key']

        # Определяем параметры в зависимости от типа шаблона
        if 'work_distance_m' in template:
            # Интервалы по дистанции (200м, 400м, 800м, 1км, 2км, 3км)
            reps_range = template['repetitions_range']
            # Подбираем кол-во повторов под доступное время
            avg_time_per_rep = 3  # минут на повтор в среднем
            max_reps = min(reps_range[1], int(main_time / avg_time_per_rep))
            reps = max(reps_range[0], max_reps)

            distance_m = template['work_distance_m']
            rest_m = template.get('rest_distance_m', 200)

            # Форматируем время работы
            time_range = template.get('work_time_range_sec', (60, 120))
            work_time_sec = (time_range[0] + time_range[1]) // 2
            work_time_formatted = f"{work_time_sec // 60}:{work_time_sec % 60:02d}" if work_time_sec >= 60 else f"{work_time_sec} сек"

            main_description = f"{reps}× {distance_m}м за ~{work_time_formatted} + {rest_m}м трусцой"

        elif 'work_time_min' in template:
            # Интервалы по времени (5 мин)
            reps_range = template['repetitions_range']
            max_reps = min(reps_range[1], int(main_time / (template['work_time_min'] + template['rest_time_min'])))
            reps = max(reps_range[0], max_reps)

            work_min = template['work_time_min']
            rest_min = template['rest_time_min']
            main_description = f"{reps}× {work_min} мин {template['hr_zone']} + {rest_min} мин трусцой"
            work_time_formatted = f"{work_min} мин"

        elif 'structure_m' in template:
            # Пирамида
            structure = template['structure_m']
            main_description = "Пирамида: " + " → ".join([f"{d}м" for d in structure])
            main_description += f"\nОтдых между отрезками = 50% времени работы"
            reps = len(structure)
            work_time_formatted = "переменное"

        elif template_key == 'fartlek':
            # Фартлек
            time_range = template['total_time_range_min']
            fartlek_time = min(time_range[1], main_time)
            main_description = f"{fartlek_time} мин переменного бега\nЧередуй: 1-3 мин быстро (Z3-Z4) / 1-2 мин легко (Z2)"
            reps = 0
            work_time_formatted = f"{fartlek_time} мин"

        else:
            # Fallback на стандартные 5 мин интервалы
            reps = max(3, min(6, int(main_time / 7.5)))
            main_description = f"{reps}× 5 мин Z4-Z5 + 2.5 мин трусцой"
            work_time_formatted = "5 мин"

        # Форматируем описание
        template_desc = template.get('description_template', '')
        if template_desc:
            try:
                tips = template_desc.format(
                    reps=reps,
                    work_time=work_time_formatted,
                    total_time=main_time
                ).strip()
            except Exception:
                tips = ""
        else:
            tips = ""

        description = f"""**{template['name']}** ({template.get('pace_zone', 'I')}-pace)

🏃 **Разминка:** {warmup} мин Z2 + 4×100м ускорения

🎯 **Основная часть:**
   {main_description}

🧘 **Заминка:** {cooldown} мин Z1-Z2

{tips}

📊 {pace_info}
💓 Пульс работы: {hr_info}
"""

        return {
            'description': description,
            'target_zone': template.get('hr_zone', 'Z4-Z5'),
            'interval_template': template_key,
        }

    def _generate_tempo(self, main_time: int, warmup: int, cooldown: int,
                       goal_type: str, pace_info: str, hr_info: str) -> Dict:
        """
        Генерация темповой тренировки

        T-темп по Daniels: "комфортно тяжело", можно держать ~60 мин
        """
        tempo_time = int(main_time * 0.6)  # 60% основной части — темп
        easy_time = main_time - tempo_time

        if goal_type == 'trail':
            description = (
                f"**Темповый бег по холмам (Threshold)**\n"
                f"- Разминка: {warmup} мин лёгкий бег\n"
                f"- {tempo_time} мин в Z3-Z4 (холмистая трасса)\n"
                f"- {easy_time} мин лёгкий бег\n"
                f"- Заминка: {cooldown} мин"
            )
        else:
            description = (
                f"**Темповый бег (Jack Daniels T-pace)**\n"
                f"- Разминка: {warmup} мин Z2\n"
                f"- {tempo_time} мин непрерывно в Z3-Z4 (Threshold)\n"
                f"- {easy_time} мин Z2\n"
                f"- Заминка: {cooldown} мин Z1-Z2"
            )

        if pace_info:
            description += f"\n- {pace_info}"
        if hr_info:
            description += f"\n- Пульс: {hr_info}"
        description += "\n- Ощущение: комфортно тяжело, короткие фразы"

        return {
            'description': description,
            'target_zone': 'Z3-Z4',
        }

    def _generate_long_run(self, main_time: int, warmup: int, cooldown: int,
                          goal_type: str, goal_distance: int, pace_info: str, hr_info: str) -> Dict:
        """
        Генерация длинной тренировки

        Правило: 30-40% недельного объёма
        """
        total_time = main_time + warmup + cooldown

        if goal_type == 'trail':
            # Для трейла — время на ногах важнее темпа
            elevation_target = int(goal_distance * 30)  # Примерно 30м набора на км
            description = (
                f"**Длинная трейловая**\n"
                f"- {total_time} мин в Z2 (разговорный темп)\n"
                f"- Цель: время на ногах, не темп\n"
                f"- Рекомендуемый набор: ~{elevation_target}м"
            )
        elif goal_distance >= 42:
            # Марафон — с марафонским темпом в конце
            mp_time = min(20, int(main_time * 0.2))
            description = (
                f"**Длинная с марафонским финишем (M-pace)**\n"
                f"- Разминка: {warmup} мин\n"
                f"- {main_time - mp_time} мин в Z2\n"
                f"- Последние {mp_time} мин: переход в Z2-Z3 (марафонский темп)\n"
                f"- Заминка: {cooldown} мин"
            )
            if self.paces:
                description += f"\n- Марафонский темп: {self.paces['marathon']}/км"
        else:
            description = (
                f"**Длинная аэробная**\n"
                f"- Разминка: {warmup} мин\n"
                f"- {main_time} мин в Z2 (разговорный темп)\n"
                f"- Заминка: {cooldown} мин"
            )

        if pace_info:
            description += f"\n- {pace_info}"
        if hr_info:
            description += f"\n- Пульс: {hr_info}"
        description += "\n- Принцип: держи разговорный темп всю тренировку"

        return {
            'description': description,
            'target_zone': 'Z2',
        }

    def _generate_recovery(self, total_time: int, pace_info: str, hr_info: str) -> Dict:
        """Генерация восстановительной тренировки"""
        description = (
            f"**Восстановительный бег**\n"
            f"- {total_time} мин очень легко в Z1\n"
            f"- Темп: медленнее обычного на 30-60 сек/км\n"
            f"- Цель: активное восстановление"
        )

        if hr_info:
            description += f"\n- Пульс: ниже {hr_info.split('-')[0]} уд/мин"

        return {
            'description': description,
            'target_zone': 'Z1',
        }

    def _generate_easy(self, main_time: int, warmup: int, cooldown: int,
                      goal_type: str, pace_info: str, hr_info: str) -> Dict:
        """Генерация лёгкой аэробной тренировки"""
        total_time = main_time + warmup + cooldown

        if goal_type == 'trail':
            description = (
                f"**Лёгкий бег по тропам**\n"
                f"- {total_time} мин в Z2\n"
                f"- Можно с небольшими подъёмами\n"
                f"- Адаптация к пересечённой местности"
            )
        else:
            description = (
                f"**Лёгкий аэробный бег (E-pace)**\n"
                f"- {total_time} мин в Z2\n"
                f"- Разговорный темп\n"
                f"- Цель: развитие аэробной базы"
            )

        if pace_info:
            description += f"\n- {pace_info}"
        if hr_info:
            description += f"\n- Пульс: {hr_info}"

        return {
            'description': description,
            'target_zone': 'Z2',
        }

    def generate_base_plan(self, goal_distance: int, goal_date: date, weeks: int = 4) -> List[Dict[str, Any]]:
        """Базовый план (обратная совместимость)"""
        return self.generate_detailed_plan(
            goal_distance=goal_distance,
            goal_date=goal_date,
            training_days=[2, 4, 6],  # Вт, Чт, Сб
            time_per_session=60,
            weeks=weeks,
            goal_type='race'
        )

    def save_plan_to_db(self, trainings: List[Dict[str, Any]]) -> int:
        """Сохранить план в БД"""
        return db.load_training_plan(self.user_id, trainings)

    def get_methodology_summary(self) -> str:
        """
        Получить саммари методологии для пользователя

        Returns:
            Текст с объяснением персонализации
        """
        lines = ["**Методология плана:**"]

        if self.vdot:
            vdot_source = self.user_settings.get('vdot_source', 'результату')
            lines.append(f"- VDOT: {self.vdot:.0f} (по {vdot_source})")
            lines.append("- Темпы рассчитаны по Jack Daniels Running Formula")

        if self.lthr:
            lines.append(f"- LTHR: {self.lthr} уд/мин")
            lines.append("- Зоны пульса по Joe Friel")

        if not self.vdot and not self.lthr:
            lines.append("- Универсальные зоны (без персонализации)")
            lines.append("- Для точных темпов синхронизируй Garmin")

        lines.append("")
        lines.append("**Принципы:**")
        lines.append("- 80/20: 80% лёгких тренировок, 20% интенсивных")
        lines.append("- Разгрузочные недели: каждая 4-я (-25% объёма)")
        lines.append("- Интервалы: оптимальный протокол 4-6×5 мин")

        return "\n".join(lines)


def create_plan_generator(user_id: int) -> PlanGenerator:
    """Создать генератор плана"""
    return PlanGenerator(user_id)
