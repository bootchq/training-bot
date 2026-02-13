"""
Калькулятор зон пульса по LTHR (Joe Friel)

=== ЧТО ТАКОЕ LTHR ===
LTHR (Lactate Threshold Heart Rate) — пульс на лактатном пороге.
Это пульс, который можно удерживать ~60 минут на максимальном усилии.

Источник: Joe Friel "The Triathlete's Training Bible"
Гайд: https://www.trainingpeaks.com/learn/articles/joe-friel-s-quick-guide-to-setting-zones/

=== КАК ОПРЕДЕЛИТЬ LTHR ===
1. 30-минутный тест на максимум (Time Trial)
2. Средний пульс последних 20 минут = LTHR
3. Или: пульс на пороговом темпе (T-pace по Jack Daniels)

=== ЗОНЫ ПО FRIEL (для БЕГА) ===
- Z1 (Recovery): <85% LTHR — активное восстановление
- Z2 (Aerobic): 85-89% LTHR — аэробная база, 80% тренировок
- Z3 (Tempo): 90-94% LTHR — темповая зона (минимизировать!)
- Z4 (SubThreshold): 95-99% LTHR — пороговые интервалы
- Z5a (SuperThreshold): 100-102% LTHR — надпороговые
- Z5b (VO2max): 103-106% LTHR — интервалы VO2max
- Z5c (Anaerobic): >106% LTHR — короткие ускорения

ВАЖНО: для велоспорта Z1 < 81% (другие пороги!)

=== ПРАВИЛО 80/20 ===
- 80% времени в Z1-Z2 (лёгкие)
- <10% в Z3 (минимизировать!)
- 20% в Z4-Z5 (интенсивные)

=== АЛЬТЕРНАТИВА: KARVONEN (Heart Rate Reserve) ===
Если есть пульс покоя (RHR) из Garmin:
Target HR = RHR + (HRR × intensity%)
Где HRR = LTHR - RHR
Более точно чем % от LTHR для тренированных бегунов

=== FALLBACK: ЗОНЫ ПО MAX HR ===
Если LTHR неизвестен:
- Z1: 50-60% HRmax
- Z2: 60-70% HRmax
- Z3: 70-80% HRmax
- Z4: 80-90% HRmax
- Z5: 90-100% HRmax
"""
from typing import Dict
from typing import Optional
from typing import Tuple

from ..utils.logger import logger

# Зоны пульса по Joe Friel (процент от LTHR) — для БЕГА
# Источник: Joe Friel "The Triathlete's Training Bible" — беговые зоны
# ВАЖНО: для бега Z1 < 85%, для велоспорта Z1 < 81%
HR_ZONES_FRIEL = {
    1: {'name': 'Recovery', 'min': 0, 'max': 85, 'description': 'Восстановление'},
    2: {'name': 'Aerobic', 'min': 85, 'max': 89, 'description': 'Аэробная база'},
    3: {'name': 'Tempo', 'min': 90, 'max': 94, 'description': 'Темповая'},
    4: {'name': 'SubThreshold', 'min': 95, 'max': 99, 'description': 'Подпороговая'},
    '5a': {'name': 'SuperThreshold', 'min': 100, 'max': 102, 'description': 'Надпороговая'},
    '5b': {'name': 'Aerobic Capacity', 'min': 103, 'max': 106, 'description': 'VO2max'},
    '5c': {'name': 'Anaerobic Capacity', 'min': 106, 'max': 120, 'description': 'Анаэробная'},
}

# Упрощённые 5 зон для бега (Joe Friel running zones)
HR_ZONES_SIMPLE = {
    1: {'name': 'Z1', 'min_pct': 0, 'max_pct': 85, 'description': 'Восстановление', 'effort': 'очень легко'},
    2: {'name': 'Z2', 'min_pct': 85, 'max_pct': 89, 'description': 'Лёгкий аэробный', 'effort': 'разговорный темп'},
    3: {'name': 'Z3', 'min_pct': 90, 'max_pct': 95, 'description': 'Темповый', 'effort': 'комфортно тяжело'},
    4: {'name': 'Z4', 'min_pct': 96, 'max_pct': 100, 'description': 'Пороговый', 'effort': 'тяжело'},
    5: {'name': 'Z5', 'min_pct': 100, 'max_pct': 110, 'description': 'VO2max / Анаэробный', 'effort': 'максимум'},
}


def calculate_hr_zones(lthr: int) -> Dict[int, Dict[str, any]]:
    """
    Рассчитать зоны пульса по LTHR

    Args:
        lthr: Lactate Threshold Heart Rate (уд/мин)

    Returns:
        Словарь зон: {1: {"name": "Z1", "min": 120, "max": 140, ...}, ...}
    """
    zones = {}

    for zone_num, zone_def in HR_ZONES_SIMPLE.items():
        min_hr = int(lthr * zone_def['min_pct'] / 100)
        max_hr = int(lthr * zone_def['max_pct'] / 100)

        zones[zone_num] = {
            'name': zone_def['name'],
            'min': min_hr,
            'max': max_hr,
            'description': zone_def['description'],
            'effort': zone_def['effort'],
            'range': f"{min_hr}-{max_hr}"
        }

    logger.info(f"Рассчитаны HR зоны по LTHR={lthr}")
    return zones


def get_zone_for_workout(workout_type: str, lthr: int) -> Tuple[int, int, str]:
    """
    Получить целевую зону пульса для типа тренировки

    Args:
        workout_type: Тип тренировки ("easy", "tempo", "intervals", "long", "recovery")
        lthr: LTHR пользователя

    Returns:
        Tuple (min_hr, max_hr, zone_name)
    """
    zones = calculate_hr_zones(lthr)

    # Маппинг типов тренировок на зоны
    workout_zones = {
        'recovery': 1,
        'easy': 2,
        'long': 2,
        'tempo': 3,
        'threshold': 4,
        'intervals': 4,
        'vo2max': 5,
        'repetition': 5,
    }

    zone_num = workout_zones.get(workout_type, 2)
    zone = zones[zone_num]

    return zone['min'], zone['max'], zone['name']


def format_hr_zones_summary(lthr: int) -> str:
    """
    Форматирование зон пульса для пользователя

    Args:
        lthr: LTHR пользователя

    Returns:
        Текст для отображения
    """
    zones = calculate_hr_zones(lthr)

    lines = [
        f"**Зоны пульса (LTHR: {lthr} уд/мин)**",
        "(рассчитаны по методологии Joe Friel)\n"
    ]

    for zone_num in sorted(zones.keys()):
        zone = zones[zone_num]
        lines.append(f"- **{zone['name']}** ({zone['range']}): {zone['description']} — {zone['effort']}")

    return "\n".join(lines)


def format_hr_range_for_workout(workout_type: str, lthr: int) -> str:
    """
    Форматирование диапазона пульса для конкретной тренировки

    Args:
        workout_type: Тип тренировки
        lthr: LTHR пользователя

    Returns:
        Строка вида "140-155 уд/мин (Z2)"
    """
    min_hr, max_hr, zone_name = get_zone_for_workout(workout_type, lthr)
    return f"{min_hr}-{max_hr} уд/мин ({zone_name})"


def estimate_lthr_from_age(age: int, fitness_level: Optional[str] = None) -> int:
    """
    Оценка LTHR по возрасту (формула Tanaka) с учётом уровня подготовки

    LTHR как % от HRmax зависит от уровня:
    - beginner: ~80% HRmax
    - intermediate: ~85% HRmax
    - advanced: ~88% HRmax

    Args:
        age: Возраст в годах
        fitness_level: Уровень подготовки (beginner/intermediate/advanced)

    Returns:
        Оценочный LTHR
    """
    # Максимальный пульс по формуле Tanaka: 208 - 0.7 * age
    max_hr = 208 - 0.7 * age

    # LTHR % от HRmax зависит от уровня подготовки
    lthr_pct = {
        'beginner': 0.80,
        'intermediate': 0.85,
        'advanced': 0.88,
    }
    pct = lthr_pct.get(fitness_level, 0.85)
    lthr = int(max_hr * pct)

    logger.info(
        f"Оценочный LTHR по возрасту {age} (уровень {fitness_level or 'default'}): "
        f"{lthr} ({pct:.0%} от max HR {int(max_hr)})"
    )
    return lthr


def calculate_hr_zones_karvonen(lthr: int, resting_hr: int) -> Dict[int, Dict[str, any]]:
    """
    Рассчитать зоны пульса по методу Karvonen (Heart Rate Reserve)

    Формула: Target HR = RHR + (HRR × intensity%)
    Где HRR = LTHR - RHR (используем LTHR вместо HRmax для беговых зон)

    Более точно чем % от LTHR, потому что учитывает
    индивидуальный пульс покоя бегуна.

    Args:
        lthr: Lactate Threshold Heart Rate (уд/мин)
        resting_hr: Пульс покоя (уд/мин)

    Returns:
        Словарь зон
    """
    hrr = lthr - resting_hr

    # Зоны по Karvonen с привязкой к Friel (для бега)
    karvonen_zones = {
        1: {'name': 'Z1', 'min_pct': 0.50, 'max_pct': 0.72, 'description': 'Восстановление', 'effort': 'очень легко'},
        2: {'name': 'Z2', 'min_pct': 0.72, 'max_pct': 0.82, 'description': 'Лёгкий аэробный', 'effort': 'разговорный темп'},
        3: {'name': 'Z3', 'min_pct': 0.82, 'max_pct': 0.90, 'description': 'Темповый', 'effort': 'комфортно тяжело'},
        4: {'name': 'Z4', 'min_pct': 0.90, 'max_pct': 1.00, 'description': 'Пороговый', 'effort': 'тяжело'},
        5: {'name': 'Z5', 'min_pct': 1.00, 'max_pct': 1.15, 'description': 'VO2max / Анаэробный', 'effort': 'максимум'},
    }

    zones = {}
    for zone_num, zone_def in karvonen_zones.items():
        min_hr = int(resting_hr + hrr * zone_def['min_pct'])
        max_hr = int(resting_hr + hrr * zone_def['max_pct'])
        zones[zone_num] = {
            'name': zone_def['name'],
            'min': min_hr,
            'max': max_hr,
            'description': zone_def['description'],
            'effort': zone_def['effort'],
            'range': f"{min_hr}-{max_hr}"
        }

    logger.info(f"Рассчитаны HR зоны Karvonen: LTHR={lthr}, RHR={resting_hr}")
    return zones


def get_workout_hr_description(workout_type: str, lthr: Optional[int]) -> str:
    """
    Получить описание пульса для тренировки

    Args:
        workout_type: Тип тренировки
        lthr: LTHR пользователя (или None)

    Returns:
        Описание целевого пульса
    """
    if lthr:
        return format_hr_range_for_workout(workout_type, lthr)
    else:
        # Общие рекомендации без персонализации (без префикса "Пульс:")
        descriptions = {
            'recovery': 'очень легко, можешь спокойно разговаривать',
            'easy': 'разговорный темп, дыхание ровное',
            'long': 'разговорный темп, комфортно на протяжении всей тренировки',
            'tempo': 'комфортно тяжело, короткие фразы',
            'threshold': 'тяжело, только отдельные слова',
            'intervals': 'тяжело во время интервала, восстановление между',
        }
        return descriptions.get(workout_type, 'по ощущениям')
