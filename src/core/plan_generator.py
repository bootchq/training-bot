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
   - Горки каждую чётную неделю (чередование hills/intervals)
   - Целевой набор высоты в длинных: ~30м/км
   - Время на ногах важнее темпа
   - Страйды после лёгких тренировок (через неделю)
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
    get_suitable_intervals,
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

        # Валидация темпов по реальным данным
        self.real_paces = self._get_real_paces_from_history()
        self.validated_paces = self._validate_paces()

    def _get_real_paces_from_history(self) -> Dict[str, int]:
        """
        Получить реальные темпы из истории тренировок.

        Returns:
            {
                'best_pace_sec': 300,      # Лучший темп (сек/км)
                'avg_easy_pace_sec': 390,  # Средний темп на лёгких (сек/км)
                'max_hr_at_best': 175,     # Пульс при лучшем темпе
            }
        """
        from ..database.db import Training
        from datetime import timedelta
        from ..utils import time_utils

        result = {
            'best_pace_sec': None,
            'avg_easy_pace_sec': None,
            'max_hr_at_best': None,
        }

        four_weeks_ago = time_utils.today() - timedelta(days=28)

        with db.get_session() as session:
            # Лучший темп за последние 4 недели (на тренировках 5+ км)
            trainings = session.query(
                Training.distance_km,
                Training.duration_min,
                Training.max_hr
            ).filter(
                Training.user_id == self.user_id,
                Training.type == 'actual',
                Training.date >= four_weeks_ago,
                Training.distance_km >= 5,
                Training.duration_min.isnot(None),
                Training.duration_min > 0
            ).all()

            if trainings:
                paces = []
                for t in trainings:
                    pace_sec = (t.duration_min * 60) / t.distance_km
                    paces.append({
                        'pace_sec': pace_sec,
                        'max_hr': t.max_hr
                    })

                if paces:
                    # Лучший темп
                    best = min(paces, key=lambda x: x['pace_sec'])
                    result['best_pace_sec'] = int(best['pace_sec'])
                    result['max_hr_at_best'] = best['max_hr']

                    # Средний темп (медиана для лёгких тренировок)
                    all_paces = sorted([p['pace_sec'] for p in paces])
                    # Берём медиану как "типичный лёгкий темп"
                    result['avg_easy_pace_sec'] = int(all_paces[len(all_paces) // 2])

        logger.info(
            f"User {self.user_id}: реальные темпы — "
            f"лучший {self._format_pace(result['best_pace_sec']) if result['best_pace_sec'] else 'N/A'}, "
            f"лёгкий {self._format_pace(result['avg_easy_pace_sec']) if result['avg_easy_pace_sec'] else 'N/A'}"
        )

        return result

    def _validate_paces(self) -> Dict[str, str]:
        """
        Валидировать VDOT-темпы по реальным данным.

        Логика:
        - Если VDOT-темп быстрее реального лучшего темпа — скорректировать
        - Интервальный темп не может быть быстрее (лучший_темп - 30 сек)
        - Easy темп не может быть быстрее реального среднего

        Returns:
            Скорректированные темпы в формате {"easy": "6:30", ...}
        """
        if not self.paces:
            return {}

        validated = dict(self.paces)  # Копия

        best_real = self.real_paces.get('best_pace_sec')
        avg_easy_real = self.real_paces.get('avg_easy_pace_sec')

        if not best_real or not avg_easy_real:
            # Нет данных — используем VDOT без изменений
            return validated

        # Получаем VDOT-темпы в секундах
        if self.vdot:
            vdot_paces_sec = get_training_paces_seconds(self.vdot)
        else:
            return validated

        corrections_made = []

        # 1. Интервальный темп: не быстрее чем (лучший_реальный - 30 сек)
        # Логика: интервальный темп должен быть достижимым, но с запасом
        min_interval_pace = best_real - 30  # Максимум на 30 сек быстрее лучшего
        if vdot_paces_sec['interval'] < min_interval_pace:
            corrected = min_interval_pace
            validated['interval'] = self._format_pace(corrected)
            corrections_made.append(f"interval: {self._format_pace(vdot_paces_sec['interval'])} → {validated['interval']}")

        # 2. Пороговый темп: не быстрее чем (лучший_реальный - 15 сек)
        min_threshold_pace = best_real - 15
        if vdot_paces_sec['threshold'] < min_threshold_pace:
            corrected = min_threshold_pace
            validated['threshold'] = self._format_pace(corrected)
            corrections_made.append(f"threshold: {self._format_pace(vdot_paces_sec['threshold'])} → {validated['threshold']}")

        # 3. Easy темп: не быстрее реального среднего
        if vdot_paces_sec['easy'] < avg_easy_real:
            corrected = avg_easy_real
            validated['easy'] = self._format_pace(corrected)
            validated['easy_range'] = f"{self._format_pace(corrected)} - {self._format_pace(int(corrected * 1.1))}"
            corrections_made.append(f"easy: {self._format_pace(vdot_paces_sec['easy'])} → {validated['easy']}")

        # 4. Марафонский темп: между easy и threshold
        # Не быстрее чем (threshold + 30 сек)
        threshold_sec = self._pace_to_seconds(validated.get('threshold', self.paces['threshold']))
        if vdot_paces_sec['marathon'] < threshold_sec + 30:
            corrected = threshold_sec + 30
            validated['marathon'] = self._format_pace(corrected)
            corrections_made.append(f"marathon: {self._format_pace(vdot_paces_sec['marathon'])} → {validated['marathon']}")

        # 5. Проверка связи темп-пульс
        # Если при лучшем темпе пульс уже был высокий (≥170) — интервальный темп должен быть консервативнее
        max_hr_at_best = self.real_paces.get('max_hr_at_best')
        if max_hr_at_best and max_hr_at_best >= 170:
            # Пользователь уже был на высоком пульсе при лучшем темпе
            # Интервальный темп не должен быть быстрее лучшего (нет запаса)
            current_interval = self._pace_to_seconds(validated.get('interval', ''))
            if current_interval and current_interval < best_real:
                validated['interval'] = self._format_pace(best_real)
                corrections_made.append(
                    f"interval (по пульсу {max_hr_at_best}): "
                    f"{self._format_pace(current_interval)} → {validated['interval']}"
                )

            # LTHR проверка: если есть LTHR и max_hr_at_best близок к нему — осторожнее
            if self.lthr and max_hr_at_best >= self.lthr * 0.95:
                # Пользователь был на пороге или выше
                # Добавляем ещё 15 сек к интервальному темпу
                current = self._pace_to_seconds(validated.get('interval', ''))
                if current:
                    validated['interval'] = self._format_pace(current + 15)
                    corrections_made.append("interval (LTHR коррекция): +15 сек")

        if corrections_made:
            logger.warning(
                f"User {self.user_id}: темпы скорректированы по реальным данным: {', '.join(corrections_made)}"
            )

        return validated

    def _format_pace(self, seconds_per_km: int) -> str:
        """Форматирование темпа в mm:ss"""
        if not seconds_per_km:
            return "N/A"
        minutes = seconds_per_km // 60
        seconds = seconds_per_km % 60
        return f"{minutes}:{seconds:02d}"

    def _pace_to_seconds(self, pace_str: str) -> int:
        """Конвертация темпа mm:ss в секунды"""
        if not pace_str or pace_str == "N/A":
            return 0
        try:
            parts = pace_str.replace('/км', '').split(':')
            return int(parts[0]) * 60 + int(parts[1])
        except (ValueError, IndexError):
            return 0

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

        # Валидация дней отдыха (минимум 2 дня, не более 3 подряд)
        training_days = self._validate_rest_days(training_days)

        # Определяем типы тренировок по правилу 80/20
        workout_schedule = self._create_80_20_schedule(training_days, weeks, goal_type=goal_type)

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

                # В разгрузочную неделю — без интервалов и горок
                if is_recovery_week and workout_type in ['intervals', 'vo2max', 'hills']:
                    workout_type = 'easy'

                # === ПРАВИЛА ДЛИТЕЛЬНОСТИ ===
                # Обычные тренировки: минимум 80 мин (включая разминку/заминку)
                # Длинный бег: 90-150 мин (разгрузка — 90, развитие — 150)
                # Восстановительный: 60 мин (единственное исключение для снижения)

                if workout_type == 'long':
                    if is_recovery_week:
                        session_time = 90  # Разгрузочная неделя
                    elif week_multiplier >= 1.1:
                        session_time = 150  # Развивающий период
                    else:
                        session_time = 120  # Базовый период
                elif workout_type == 'recovery':
                    session_time = 60  # Восстановительный — минимум 60
                else:
                    # Обычные тренировки (easy, intervals, tempo, hills): 80 мин
                    session_time = 80

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
        """Определить уровень подготовки с учётом стабильности"""
        from ..core.stats_calculator import StatsCalculator

        calculator = StatsCalculator(self.user_id)
        stats = calculator.get_month_stats()

        if stats['trainings_count'] > 0:
            # Автоопределение по истории
            avg_weekly = stats['total_distance'] / 4

            # Проверка стабильности: сколько недель реально тренировался
            # Если <1.5 тренировки в неделю в среднем — понизить уровень
            avg_weekly_sessions = stats['trainings_count'] / 4
            is_inconsistent = avg_weekly_sessions < 1.5

            if avg_weekly < 20 or is_inconsistent:
                return 'beginner'
            elif avg_weekly < 40:
                return 'intermediate'
            else:
                return 'advanced'

        return explicit_level or 'beginner'

    def _get_level_multiplier(self, level: str) -> float:
        """Множитель времени по уровню с учётом стабильности"""
        from ..core.stats_calculator import StatsCalculator

        base_multipliers = {
            'beginner': 0.85,
            'intermediate': 1.0,
            'advanced': 1.15
        }
        multiplier = base_multipliers.get(level, 1.0)

        # Дополнительная коррекция для нестабильных бегунов
        try:
            calculator = StatsCalculator(self.user_id)
            stats = calculator.get_month_stats()
            if stats['trainings_count'] > 0:
                avg_weekly_sessions = stats['trainings_count'] / 4
                # Менее 2 тренировок в неделю → снижаем на 15%
                if avg_weekly_sessions < 2:
                    multiplier *= 0.85
                    logger.info(
                        f"User {self.user_id}: стабильность {avg_weekly_sessions:.1f} тр/нед "
                        f"→ множитель снижен до {multiplier:.2f}"
                    )
        except Exception:
            pass

        return multiplier

    def _get_workout_goal(self, workout_type: str) -> str:
        """Получить цель тренировки для отображения пользователю"""
        goals = {
            'intervals': "Цель: Повышение VO2max — рост выносливости",
            'vo2max': "Цель: Повышение VO2max — рост выносливости",
            'hills': "Цель: Сила ног и горная специфика — подготовка к трейлу",
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

    def _create_80_20_schedule(self, training_days: List[int], weeks: int,
                               goal_type: str = 'race') -> Dict[tuple, str]:
        """
        Создать расписание по правилу 80/20

        80% тренировок — лёгкие (easy, long, recovery)
        20% тренировок — интенсивные (intervals, tempo, threshold)

        Умный порядок дней:
        - Long → самый поздний день (выходной)
        - Intervals/Hills → средний день (середина недели)
        - Easy → самый ранний день
        """
        schedule = {}
        num_days = len(training_days)
        sorted_days = sorted(training_days)

        # Распределение типов тренировок по количеству дней
        if num_days <= 2:
            types_ordered = ['easy', 'long']
        elif num_days == 3:
            types_ordered = ['easy', 'intervals', 'long']
        elif num_days == 4:
            types_ordered = ['easy', 'intervals', 'easy', 'long']
        elif num_days == 5:
            types_ordered = ['easy', 'intervals', 'easy', 'easy', 'long']
        else:
            types_ordered = ['easy', 'intervals', 'easy', 'tempo', 'long', 'recovery']
            types_ordered = types_ordered[:num_days]

        # Маппинг: тип → позиция в sorted_days
        # Long → последний день, Intervals/Hills → средний, Easy → ранний
        day_to_type = {}
        for i, day_num in enumerate(sorted_days):
            day_to_type[day_num] = types_ordered[i] if i < len(types_ordered) else 'easy'

        for week_num in range(weeks):
            for day_num in sorted_days:
                workout_type = day_to_type[day_num]

                # Для trail: чередование hills/intervals (нечётная=hills, чётная=intervals)
                if goal_type == 'trail' and workout_type == 'intervals':
                    if week_num % 2 == 0:
                        workout_type = 'hills'
                    # Нечётные недели оставляем intervals

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

        if workout_type == 'hills':
            details = self._generate_hills(main_time, warmup, cooldown,
                                           'medium_hills', pace_info, hr_info)
        elif workout_type == 'intervals' or workout_type == 'vo2max':
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
            details = self._generate_easy(main_time, warmup, cooldown, goal_type, pace_info, hr_info,
                                          is_recovery_week=is_recovery_week, week_num=week_num)

        # Расчёт дистанции
        details['distance_km'] = self._calculate_distance(total_time, workout_type, base_pace)
        details['total_time'] = total_time

        return details

    def _get_pace_info(self, workout_type: str) -> str:
        """Получить информацию о темпе (валидированном по реальным данным)"""
        # Используем валидированные темпы если есть, иначе VDOT
        paces = self.validated_paces if self.validated_paces else self.paces
        if not paces:
            return ""

        pace_mapping = {
            'easy': f"Темп: {paces.get('easy_range', paces.get('easy', 'N/A'))}/км",
            'recovery': f"Темп: медленнее {paces.get('easy', 'N/A')}/км",
            'long': f"Темп: {paces.get('easy_range', paces.get('easy', 'N/A'))}/км",
            'tempo': f"Темп: {paces.get('threshold', 'N/A')}/км",
            'threshold': f"Темп: {paces.get('threshold', 'N/A')}/км",
            'intervals': f"Темп интервалов: {paces.get('interval', 'N/A')}/км",
            'vo2max': f"Темп интервалов: {paces.get('interval', 'N/A')}/км",
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
            'hills': 1.1,
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

            # Получаем темп (валидированный по реальным данным)
            pace_zone = template.get('pace_zone', 'I')
            if self.validated_paces or self.vdot:
                # Сначала пробуем валидированные темпы
                if self.validated_paces:
                    if pace_zone == 'R':
                        pace_sec_per_km = self._pace_to_seconds(self.validated_paces.get('repetition', ''))
                    elif pace_zone == 'T':
                        pace_sec_per_km = self._pace_to_seconds(self.validated_paces.get('threshold', ''))
                    else:  # I по умолчанию
                        pace_sec_per_km = self._pace_to_seconds(self.validated_paces.get('interval', ''))

                # Если валидированные не сработали — используем VDOT
                if not pace_sec_per_km and self.vdot:
                    paces_sec = get_training_paces_seconds(self.vdot)
                    if pace_zone == 'R':
                        pace_sec_per_km = paces_sec['repetition']
                    elif pace_zone == 'T':
                        pace_sec_per_km = paces_sec['threshold']
                    else:
                        pace_sec_per_km = paces_sec['interval']
            else:
                pace_sec_per_km = None

            if not pace_sec_per_km:
                # Fallback на расчёт из шаблона (если VDOT не задан)
                time_range = template.get('work_time_range_sec', (60, 120))
                work_time_sec = (time_range[0] + time_range[1]) // 2
                pace_sec_per_km = int(work_time_sec * 1000 / distance_m)

            pace_min = pace_sec_per_km // 60
            pace_sec = pace_sec_per_km % 60
            pace_formatted = f"{pace_min}:{pace_sec:02d}/км"

            main_description = f"{reps}× {distance_m}м в темпе {pace_formatted} + {rest_m}м трусцой"

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
            main_description += "\nОтдых между отрезками = 50% времени работы"
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

        # Извлекаем только советы (💡 и ⚠️) из tips
        tip_lines = []
        if tips:
            for line in tips.split('\n'):
                line = line.strip()
                if line.startswith('💡') or line.startswith('⚠️'):
                    tip_lines.append(line)

        description = f"""**{template['name']}** ({template.get('pace_zone', 'I')}-pace)
- Разминка: {warmup} мин Z2 + 4×100м ускорения
- Основная часть: {main_description}
- Заминка: {cooldown} мин Z1-Z2
- {pace_info}
- Пульс: {hr_info}

{chr(10).join(tip_lines)}"""

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

        description += "\n\n💡 Комфортно тяжело — можешь говорить короткими фразами, но не предложениями\n⚠️ Если «умираешь» к концу — начал слишком быстро"

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
            # Целевой набор для длинной: ~30м на каждый км дистанции тренировки
            distance_estimate = total_time / 7.5  # км примерно
            training_elev = int(distance_estimate * 30)
            description = (
                f"**Длинная трейловая**\n"
                f"- {total_time} мин в Z2 (разговорный темп)\n"
                f"- Целевой набор высоты: ~{training_elev}м\n"
                f"- Шагай в крутые горки (>15%), бежай пологие (<10%)\n"
                f"- На спусках: короткий шаг, мягкое приземление\n"
                f"- Бери воду если >90 мин"
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

        description += "\n\n💡 Главное — время на ногах. Не гонись за темпом\n⚠️ Возьми воду и гели если бежишь дольше 90 мин"

        return {
            'description': description,
            'target_zone': 'Z2',
        }

    def _generate_recovery(self, total_time: int, pace_info: str, hr_info: str) -> Dict:
        """Генерация восстановительной тренировки"""
        description = (
            f"**Восстановительный бег**\n"
            f"- {total_time} мин очень легко в Z1\n"
            f"- Темп: медленнее обычного на 30-60 сек/км"
        )

        if hr_info:
            # Если есть числовой диапазон (LTHR), берём нижнюю границу
            if '-' in hr_info and hr_info.split('-')[0].isdigit():
                description += f"\n- Пульс: ниже {hr_info.split('-')[0]} уд/мин"
            else:
                description += f"\n- Пульс: {hr_info}"

        description += "\n\n💡 Это не тренировка — это восстановление. Беги максимально легко\n⚠️ Если чувствуешь усталость — лучше пройтись или отдохнуть"

        return {
            'description': description,
            'target_zone': 'Z1',
        }

    def _generate_easy(self, main_time: int, warmup: int, cooldown: int,
                      goal_type: str, pace_info: str, hr_info: str,
                      is_recovery_week: bool = False, week_num: int = 0) -> Dict:
        """Генерация лёгкой аэробной тренировки"""
        total_time = main_time + warmup + cooldown

        if goal_type == 'trail':
            description = (
                f"**Лёгкий бег по тропам**\n"
                f"- {total_time} мин в Z2\n"
                f"- Можно с небольшими подъёмами"
            )
            tips = "💡 Слушай тело — на подъёмах можно переходить на шаг\n⚠️ Не гонись за темпом, важно время на ногах"
        else:
            description = (
                f"**Лёгкий аэробный бег (E-pace)**\n"
                f"- {total_time} мин в Z2\n"
                f"- Разговорный темп"
            )
            tips = "💡 Должен мочь разговаривать полными предложениями\n⚠️ Если дыхание сбивается — сбавь темп"

        if pace_info:
            description += f"\n- {pace_info}"
        if hr_info:
            description += f"\n- Пульс: {hr_info}"

        # Страйды через неделю (не в разгрузочную)
        if not is_recovery_week and week_num % 2 == 0:
            description += "\n\nПосле бега: 4-6x100м страйды (Z5, 15-20 сек, полное восстановление)"

        description += f"\n\n{tips}"

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
