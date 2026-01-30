"""
Калькулятор зон пульса по LTHR (Joe Friel)

LTHR (Lactate Threshold Heart Rate) — пульс на лактатном пороге.
Зоны рассчитываются как процент от LTHR.

Источник: Joe Friel "The Triathlete's Training Bible"
"""
from typing import Dict, List, Tuple, Optional
from ..utils.logger import logger


# Зоны пульса по Joe Friel (процент от LTHR)
HR_ZONES_FRIEL = {
    1: {'name': 'Recovery', 'min': 0, 'max': 81, 'description': 'Восстановление'},
    2: {'name': 'Aerobic', 'min': 81, 'max': 89, 'description': 'Аэробная база'},
    3: {'name': 'Tempo', 'min': 90, 'max': 93, 'description': 'Темповая'},
    4: {'name': 'SubThreshold', 'min': 94, 'max': 99, 'description': 'Подпороговая'},
    '5a': {'name': 'SuperThreshold', 'min': 100, 'max': 102, 'description': 'Надпороговая'},
    '5b': {'name': 'Aerobic Capacity', 'min': 103, 'max': 106, 'description': 'VO2max'},
    '5c': {'name': 'Anaerobic Capacity', 'min': 106, 'max': 120, 'description': 'Анаэробная'},
}

# Упрощённые 5 зон (более понятные для пользователя)
HR_ZONES_SIMPLE = {
    1: {'name': 'Z1', 'min_pct': 0, 'max_pct': 81, 'description': 'Восстановление', 'effort': 'очень легко'},
    2: {'name': 'Z2', 'min_pct': 81, 'max_pct': 89, 'description': 'Лёгкий аэробный', 'effort': 'разговорный темп'},
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
        f"(рассчитаны по методологии Joe Friel)\n"
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


def estimate_lthr_from_age(age: int) -> int:
    """
    Оценка LTHR по возрасту (формула Tanaka)
    Используется если нет данных из Garmin

    Args:
        age: Возраст в годах

    Returns:
        Оценочный LTHR
    """
    # Максимальный пульс по формуле Tanaka: 208 - 0.7 * age
    max_hr = 208 - 0.7 * age

    # LTHR обычно составляет 85-90% от max HR для тренированных
    # Для менее тренированных ~80%
    lthr = int(max_hr * 0.85)

    logger.info(f"Оценочный LTHR по возрасту {age}: {lthr} (max HR: {int(max_hr)})")
    return lthr


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
        hr_range = format_hr_range_for_workout(workout_type, lthr)
        return f"Пульс: {hr_range}"
    else:
        # Общие рекомендации без персонализации
        descriptions = {
            'recovery': 'Пульс: очень легко, можешь спокойно разговаривать',
            'easy': 'Пульс: разговорный темп, дыхание ровное',
            'long': 'Пульс: разговорный темп, комфортно на протяжении всей тренировки',
            'tempo': 'Пульс: комфортно тяжело, короткие фразы',
            'threshold': 'Пульс: тяжело, только отдельные слова',
            'intervals': 'Пульс: тяжело во время интервала, восстановление между',
        }
        return descriptions.get(workout_type, 'Пульс: по ощущениям')
