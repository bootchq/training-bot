"""
Шаблоны тренировок: интервалы, горки, силовые

=== МЕТОДОЛОГИЯ (гибридный подход) ===

Источники:
- Jack Daniels "Running Formula" (2021, 4th ed): VDOT, 5 зон темпов (E/M/T/I/R)
- Matt Fitzgerald "80/20 Running": 80% лёгких, 20% интенсивных
- Norwegian Model (Marius Bakken, 2025): двойной порог, лактат 2-4 ммоль/л
- Kenyan Methods (Kipchoge): 200+ км/нед, только 15-20% высокой интенсивности
- Pete Pfitzinger "Advanced Marathoning" (2025, 4th ed): 5 мезоциклов
- Renato Canova: специфичность к дистанции

Ключевые принципы:
1. 80/20: 80% тренировок в Z1-Z2, 20% в Z4-Z5, минимум Z3
2. Периодизация: BASE (60%) → BUILD (30%) → PEAK (10%)
3. Ротация: не повторять формат интервалов 2 недели подряд
4. Восстановление: мин. 2 дня отдыха/неделю, после длинной — обязательно
5. Разгрузка: каждая 4-я неделя -25% объёма

Интервалы по периодам:
- BASE: VO2max (800м, 1км, 5мин) — развитие аэробной мощности
- BUILD: mix (400м, ПАНО 2-3км, пирамида, cruise) — специфичность
- PEAK: короткие (200м, 400м, фартлек) — нервная система, свежесть

Зоны темпов (Jack Daniels):
- E (Easy): 65-79% HRmax, разговорный темп
- M (Marathon): целевой темп марафона
- T (Threshold): "комфортно тяжело", ~60 мин удержания
- I (Interval): 97-100% VO2max, 3-5 мин интервалы
- R (Repetition): быстрее 5k, нейромышечная работа

Научная база:
- 80/20: исследование 120 бегунов показало +11.3 мин на марафоне (Nature, 2025)
- VO2max интервалы: 4×5 мин с 2.5 мин отдыхом — оптимальный протокол
- Элита: 78% объёма медленнее марафонского темпа (исследование 2024)
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class IntervalFocus(str, Enum):
    """Фокус интервальной тренировки"""
    SPEED = "speed"           # Скорость, нервная система
    VO2MAX = "vo2max"         # Максимальное потребление кислорода
    THRESHOLD = "threshold"   # Лактатный порог (ПАНО)
    ENDURANCE = "endurance"   # Выносливость
    MIXED = "mixed"           # Смешанный


class TrainingPeriod(str, Enum):
    """Период подготовки"""
    BASE = "base"         # Базовый (60% цикла)
    BUILD = "build"       # Развивающий (30% цикла)
    PEAK = "peak"         # Подводка (10% цикла)
    RECOVERY = "recovery" # Восстановительная неделя


# =============================================================================
# ШАБЛОНЫ ИНТЕРВАЛОВ
# =============================================================================

INTERVAL_TEMPLATES: Dict[str, Dict] = {
    # --- Короткие (скорость, R-pace) ---
    'speed_200': {
        'name': 'Ритм 200м',
        'name_en': 'Speed 200m',
        'work_distance_m': 200,
        'rest_distance_m': 200,
        'work_time_range_sec': (43, 48),  # темп ~3:35-4:00/км
        'repetitions_range': (10, 15),
        'pace_zone': 'R',  # Repetition (Jack Daniels)
        'hr_zone': 'Z5',
        'focus': IntervalFocus.SPEED,
        'suitable_periods': [TrainingPeriod.BUILD, TrainingPeriod.PEAK],
        'description_template': """
🎯 **{reps}× 200м** за {work_time} сек + 200м трусцой

💡 Быстро, но расслабленно. Фокус на технике, не на скорости.
⚠️ Если последние повторы медленнее первых на >3 сек — слишком быстро начал.
""",
    },

    'speed_400': {
        'name': 'Ритм 400м',
        'name_en': 'Speed 400m',
        'work_distance_m': 400,
        'rest_distance_m': 200,
        'work_time_range_sec': (95, 104),  # 1:35-1:44
        'repetitions_range': (6, 8),
        'pace_zone': 'R',
        'hr_zone': 'Z4-Z5',
        'focus': IntervalFocus.SPEED,
        'suitable_periods': [TrainingPeriod.BUILD, TrainingPeriod.PEAK],
        'description_template': """
🎯 **{reps}× 400м** за {work_time} + 200м трусцой

💡 Контролируемая скорость. Первые 200м — накат, вторые — держать.
⚠️ Не спринт! Должен мочь повторить.
""",
    },

    # --- Средние (VO2max, I-pace) ---
    'vo2max_800': {
        'name': 'Средние 800м',
        'name_en': 'VO2max 800m',
        'work_distance_m': 800,
        'rest_distance_m': 400,
        'work_time_range_sec': (195, 210),  # 3:15-3:30
        'repetitions_range': (4, 6),
        'pace_zone': 'I',  # Interval (Jack Daniels)
        'hr_zone': 'Z4',
        'focus': IntervalFocus.VO2MAX,
        'suitable_periods': [TrainingPeriod.BASE, TrainingPeriod.BUILD],
        'description_template': """
🎯 **{reps}× 800м** за {work_time} + 400м трусцой

💡 Темп "комфортно тяжело". Дыхание учащённое, но контролируемое.
⚠️ Отдых — активный! Трусца, не ходьба.
""",
    },

    'vo2max_1k': {
        'name': 'Средние 1км',
        'name_en': 'VO2max 1km',
        'work_distance_m': 1000,
        'rest_distance_m': 400,
        'work_time_range_sec': (255, 280),  # 4:15-4:40
        'repetitions_range': (4, 5),
        'pace_zone': 'I',
        'hr_zone': 'Z4',
        'focus': IntervalFocus.VO2MAX,
        'suitable_periods': [TrainingPeriod.BASE, TrainingPeriod.BUILD],
        'description_template': """
🎯 **{reps}× 1км** за {work_time} + 400м трусцой

💡 Золотой стандарт VO2max работы. Держи ровный темп всю дистанцию.
⚠️ Первый км — не быстрее последнего!
""",
    },

    'vo2max_5min': {
        'name': 'VO2max 5 мин',
        'name_en': 'VO2max 5min',
        'work_time_min': 5,
        'rest_time_min': 2.5,
        'repetitions_range': (3, 6),
        'pace_zone': 'I',
        'hr_zone': 'Z4',
        'focus': IntervalFocus.VO2MAX,
        'suitable_periods': [TrainingPeriod.BASE, TrainingPeriod.BUILD],
        'description_template': """
🎯 **{reps}× 5 мин** в Z4 + 2.5 мин трусцой

💡 Классика Jack Daniels. К концу интервала пульс должен достичь Z4.
⚠️ Если пульс не поднимается — беги быстрее. Если зашкаливает — медленнее.
""",
    },

    # --- Длинные (ПАНО, T-pace) ---
    'threshold_2k': {
        'name': 'ПАНО 2км',
        'name_en': 'Threshold 2km',
        'work_distance_m': 2000,
        'rest_distance_m': 500,
        'work_time_range_sec': (570, 620),  # 9:30-10:20 (4:45-5:10/км)
        'repetitions_range': (3, 4),
        'pace_zone': 'T',  # Threshold (Jack Daniels)
        'hr_zone': 'Z3-Z4',
        'focus': IntervalFocus.THRESHOLD,
        'suitable_periods': [TrainingPeriod.BUILD],
        'description_template': """
🎯 **{reps}× 2км** за {work_time} + 500м лёгкой трусцой

💡 Пороговый темп: можешь говорить короткими фразами, но не предложениями.
⚠️ Темп должен быть устойчивым. Если "умираешь" к концу — начал слишком быстро.
""",
    },

    'threshold_3k': {
        'name': 'ПАНО 3км',
        'name_en': 'Threshold 3km',
        'work_distance_m': 3000,
        'rest_distance_m': 1000,
        'work_time_range_sec': (900, 990),  # 15:00-16:30
        'repetitions_range': (2, 3),
        'pace_zone': 'T',
        'hr_zone': 'Z3-Z4',
        'focus': IntervalFocus.THRESHOLD,
        'suitable_periods': [TrainingPeriod.BUILD],
        'description_template': """
🎯 **{reps}× 3км** за {work_time} + 1км лёгкой трусцой

💡 Длинная пороговая работа. Развивает способность держать темп.
⚠️ Ментально тяжело. Разбей на сегменты: первый км — вкатиться, второй — держать, третий — не сдаваться.
""",
    },

    # --- Специальные форматы ---
    'pyramid': {
        'name': 'Пирамида',
        'name_en': 'Pyramid',
        'structure_m': [200, 400, 800, 400, 200],  # метры
        'rest_ratio': 0.5,  # отдых = 50% от времени работы
        'pace_zone': 'I',
        'hr_zone': 'Z4',
        'focus': IntervalFocus.MIXED,
        'suitable_periods': [TrainingPeriod.BUILD, TrainingPeriod.PEAK],
        'description_template': """
🎯 **Пирамида:** 200м → 400м → 800м → 400м → 200м
   Отдых между отрезками = половина времени работы

💡 Разнообразие! Короткие — быстрее (R-pace), длинные — медленнее (I-pace).
⚠️ 800м — ключевой отрезок. Не начинай слишком быстро.
""",
    },

    'fartlek': {
        'name': 'Фартлек',
        'name_en': 'Fartlek',
        'total_time_range_min': (25, 40),
        'work_rest_pattern': 'variable',  # переменный
        'pace_zone': 'mixed',
        'hr_zone': 'Z2-Z4',
        'focus': IntervalFocus.ENDURANCE,
        'suitable_periods': [TrainingPeriod.BASE, TrainingPeriod.BUILD, TrainingPeriod.PEAK],
        'description_template': """
🎯 **Фартлек {total_time} мин**
   Чередуй: 1-3 мин быстро (Z3-Z4) / 1-2 мин легко (Z2)
   Ориентируйся на ощущения, не на часы

💡 "Игра скоростей". Бегай по рельефу: в горку — быстрее, с горки — отдых.
⚠️ Нет жёстких правил. Слушай тело.
""",
    },

    'cruise_intervals': {
        'name': 'Круизные интервалы',
        'name_en': 'Cruise Intervals',
        'work_time_min': 10,
        'rest_time_min': 2,
        'repetitions_range': (3, 4),
        'pace_zone': 'T',
        'hr_zone': 'Z3',
        'focus': IntervalFocus.THRESHOLD,
        'suitable_periods': [TrainingPeriod.BUILD],
        'description_template': """
🎯 **{reps}× 10 мин** в T-pace + 2 мин трусцой

💡 Длинные пороговые интервалы. Отличная подготовка к темповым забегам.
⚠️ Темп должен быть "комфортно тяжёлым" — не спринт, но и не прогулка.
""",
    },
}


# =============================================================================
# ШАБЛОНЫ ГОРОК (для трейла)
# =============================================================================

HILL_TEMPLATES: Dict[str, Dict] = {
    'short_hills': {
        'name': 'Короткие горки',
        'name_en': 'Short Hills',
        'work_distance_m': (200, 300),
        'gradient_percent': (8, 12),
        'repetitions_range': (8, 12),
        'focus': 'power',
        'recovery': 'jog_down',
        'description_template': """
🏔️ **{reps}× {distance}м** в гору ({gradient}% уклон)
   Спуск — лёгкой трусцой (восстановление)

💡 Взрывная работа! Короткие ноги, активная работа рук, взгляд вперёд.
⚠️ Не "умирай" на вершине — контролируй усилие.
""",
    },

    'medium_hills': {
        'name': 'Средние горки',
        'name_en': 'Medium Hills',
        'work_distance_m': (400, 600),
        'gradient_percent': (6, 10),
        'repetitions_range': (6, 8),
        'focus': 'strength_endurance',
        'recovery': 'jog_down',
        'description_template': """
🏔️ **{reps}× {distance}м** в гору ({gradient}% уклон)
   Спуск — трусцой

💡 Силовая выносливость. Ритмичное дыхание, стабильный каденс.
⚠️ Темп ниже чем на коротких — нужно добежать!
""",
    },

    'long_hills': {
        'name': 'Длинные подъёмы',
        'name_en': 'Long Climbs',
        'work_time_min': (3, 5),
        'gradient_percent': (4, 8),
        'repetitions_range': (4, 6),
        'focus': 'climbing_endurance',
        'recovery': 'walk_jog_down',
        'description_template': """
🏔️ **{reps}× {time} мин** в гору ({gradient}% уклон)
   Спуск — ходьба/лёгкая трусца

💡 Имитация трейловых подъёмов. Можно переходить на power hike (быстрая ходьба).
⚠️ На длинных подъёмах эффективнее идти быстро, чем бежать медленно.
""",
    },

    'downhill_focus': {
        'name': 'Спуски (квадрицепсы)',
        'name_en': 'Downhill Focus',
        'descent_distance_m': (400, 800),
        'gradient_percent': (6, 10),
        'repetitions_range': (6, 10),
        'focus': 'eccentric_strength',
        'recovery': 'easy_climb',
        'description_template': """
🏔️ **{reps}× {distance}м спуска** ({gradient}% уклон)
   Подъём — лёгким бегом/ходьбой

💡 Тренировка квадрицепсов на эксцентрику. Короткие шаги, мягкое приземление.
⚠️ Не тормози пятками! Приземляйся на середину стопы.
""",
    },

    'vertical_gain': {
        'name': 'Набор высоты',
        'name_en': 'Vertical Gain Session',
        'target_elevation_m': (300, 600),
        'focus': 'total_climbing',
        'recovery': 'continuous',
        'description_template': """
🏔️ **Цель: {elevation}м набора высоты**
   Любая комбинация подъёмов (повторы или один длинный)

💡 Главное — суммарный набор, не скорость. Практика питания и палок.
⚠️ Следи за пульсом на подъёмах — не уходи в красную зону надолго.
""",
    },
}


# =============================================================================
# ШАБЛОНЫ СИЛОВЫХ ТРЕНИРОВОК
# =============================================================================

STRENGTH_TEMPLATES: Dict[str, Dict] = {
    'gym_ofp': {
        'name': 'ОФП в зале',
        'name_en': 'Gym Strength',
        'duration_min': 45,
        'type': 'gym',
        'exercises': [
            {'name': 'Полуприседы со штангой', 'sets': 3, 'reps': 12, 'weight': '40кг'},
            {'name': 'Жим ногами', 'sets': 3, 'reps': 15, 'notes': 'Медленно вниз'},
            {'name': 'Сгибание ног на тренажёре', 'sets': 3, 'reps': 12},
            {'name': 'Разгибание ног на тренажёре', 'sets': 3, 'reps': 12},
            {'name': 'Гиперэкстензия', 'sets': 3, 'reps': 15},
            {'name': 'Планка', 'sets': 3, 'time': '60 сек'},
            {'name': 'Скручивания', 'sets': 3, 'reps': 20},
        ],
        'description_template': """
💪 **ОФП в зале** (~{duration} мин)

📋 Упражнения:
{exercises_list}

💡 Отдых между подходами: 60-90 сек
⚠️ Не делай силовую накануне интервалов!
""",
    },

    'sbu_drills': {
        'name': 'СБУ / Техническая',
        'name_en': 'Running Drills',
        'duration_min': 30,
        'type': 'drills',
        'exercises': [
            {'name': 'Разминка лёгкий бег', 'time': '10 мин'},
            {'name': 'Перекаты с пятки на носок', 'sets': 2, 'distance': '30м'},
            {'name': 'Высокое бедро', 'sets': 3, 'distance': '30м'},
            {'name': 'Захлёст голени', 'sets': 3, 'distance': '30м'},
            {'name': 'Олений бег', 'sets': 3, 'distance': '30м'},
            {'name': 'Прыжки в шаге', 'sets': 3, 'distance': '30м'},
            {'name': 'Ускорения', 'sets': 5, 'distance': '60м'},
            {'name': 'Заминка', 'time': '5 мин'},
        ],
        'description_template': """
🏃 **СБУ / Техническая** (~{duration} мин)

📋 Программа:
{exercises_list}

💡 После каждого упражнения (кроме ускорений) — 20м лёгкого бега
⚠️ Фокус на технике, не на скорости!
""",
    },

    'outdoor_ofp': {
        'name': 'ОФП на улице',
        'name_en': 'Outdoor Strength',
        'duration_min': 40,
        'type': 'outdoor',
        'exercises': [
            {'name': 'Разминка', 'time': '5 мин'},
            {'name': 'Берпи', 'sets': 3, 'reps': 10},
            {'name': 'Выпады с шагом', 'sets': 3, 'reps': '20 каждой ногой'},
            {'name': 'Приседания с выпрыгиванием', 'sets': 3, 'reps': 15},
            {'name': 'Подтягивания', 'sets': 3, 'reps': 'max'},
            {'name': 'Отжимания', 'sets': 3, 'reps': 20},
            {'name': 'Планка боковая', 'sets': 3, 'time': '30 сек каждая сторона'},
            {'name': 'Заминка + растяжка', 'time': '5 мин'},
        ],
        'description_template': """
💪 **ОФП на улице** (~{duration} мин)

📋 Круговая тренировка:
{exercises_list}

💡 Минимальный отдых между упражнениями (30 сек)
⚠️ Можно делать после лёгкого бега
""",
    },

    'core_stability': {
        'name': 'Кор и стабилизация',
        'name_en': 'Core Stability',
        'duration_min': 20,
        'type': 'core',
        'exercises': [
            {'name': 'Планка фронтальная', 'sets': 3, 'time': '45 сек'},
            {'name': 'Планка боковая (левая)', 'sets': 3, 'time': '30 сек'},
            {'name': 'Планка боковая (правая)', 'sets': 3, 'time': '30 сек'},
            {'name': 'Мёртвый жук (dead bug)', 'sets': 3, 'reps': 10},
            {'name': 'Ягодичный мост', 'sets': 3, 'reps': 15},
            {'name': 'Bird-dog', 'sets': 3, 'reps': '10 каждая сторона'},
        ],
        'description_template': """
🧘 **Кор и стабилизация** (~{duration} мин)

📋 Упражнения:
{exercises_list}

💡 Можно делать каждый день (утром или вечером)
⚠️ Дыхание ровное, не задерживай!
""",
    },
}


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================

def get_suitable_intervals(period: TrainingPeriod,
                           recent_used: Optional[List[str]] = None) -> List[str]:
    """
    Получить подходящие шаблоны интервалов для периода подготовки

    Args:
        period: Текущий период подготовки
        recent_used: Список недавно использованных шаблонов (исключаем)

    Returns:
        Список ключей подходящих шаблонов
    """
    recent_used = recent_used or []
    suitable = []

    for key, template in INTERVAL_TEMPLATES.items():
        if period in template.get('suitable_periods', []):
            if key not in recent_used[-2:]:  # Не повторять последние 2
                suitable.append(key)

    # Если всё исключено, вернуть все подходящие
    if not suitable:
        suitable = [k for k, t in INTERVAL_TEMPLATES.items()
                   if period in t.get('suitable_periods', [])]

    return suitable


def format_interval_description(template_key: str,
                                reps: int,
                                work_time_formatted: str,
                                pace_per_km: str,
                                hr_range: str) -> str:
    """
    Форматировать описание интервальной тренировки

    Args:
        template_key: Ключ шаблона из INTERVAL_TEMPLATES
        reps: Количество повторений
        work_time_formatted: Время работы (например "1:42")
        pace_per_km: Темп (например "4:15/км")
        hr_range: Диапазон пульса (например "155-170")

    Returns:
        Отформатированное описание
    """
    template = INTERVAL_TEMPLATES.get(template_key)
    if not template:
        return f"Интервалы: {reps} повторов"

    base_desc = template['description_template'].format(
        reps=reps,
        work_time=work_time_formatted,
        total_time=reps * 5  # примерно
    )

    return f"""**{template['name']}** ({template['pace_zone']}-pace)

🏃 **Разминка:** 15 мин Z2 + 4×100м ускорения
{base_desc}
🧘 **Заминка:** 10 мин Z1-Z2

📊 Темп интервалов: {pace_per_km}
💓 Пульс работы: {hr_range} уд/мин
"""


def format_strength_description(template_key: str) -> str:
    """
    Форматировать описание силовой тренировки

    Args:
        template_key: Ключ шаблона из STRENGTH_TEMPLATES

    Returns:
        Отформатированное описание
    """
    template = STRENGTH_TEMPLATES.get(template_key)
    if not template:
        return "Силовая тренировка"

    # Форматируем список упражнений
    exercises_lines = []
    for ex in template['exercises']:
        line = f"  • {ex['name']}"
        if 'sets' in ex and 'reps' in ex:
            line += f" — {ex['sets']}×{ex['reps']}"
        elif 'sets' in ex and 'time' in ex:
            line += f" — {ex['sets']}×{ex['time']}"
        elif 'time' in ex:
            line += f" — {ex['time']}"
        if 'weight' in ex:
            line += f" ({ex['weight']})"
        if 'notes' in ex:
            line += f" [{ex['notes']}]"
        exercises_lines.append(line)

    exercises_list = '\n'.join(exercises_lines)

    return template['description_template'].format(
        duration=template['duration_min'],
        exercises_list=exercises_list
    )


def format_hill_description(template_key: str,
                            reps: int,
                            distance_or_time: str,
                            gradient: int,
                            elevation: Optional[int] = None) -> str:
    """
    Форматировать описание горной тренировки

    Args:
        template_key: Ключ шаблона из HILL_TEMPLATES
        reps: Количество повторений
        distance_or_time: Дистанция или время
        gradient: Уклон в процентах
        elevation: Целевой набор высоты (для vertical_gain)

    Returns:
        Отформатированное описание
    """
    template = HILL_TEMPLATES.get(template_key)
    if not template:
        return f"Горки: {reps} повторов"

    return template['description_template'].format(
        reps=reps,
        distance=distance_or_time,
        time=distance_or_time,
        gradient=gradient,
        elevation=elevation or 400
    )
