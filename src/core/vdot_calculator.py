"""
Калькулятор VDOT по методологии Jack Daniels

VDOT — это индекс беговой формы, позволяющий рассчитать оптимальные
тренировочные темпы на основе результата на любой дистанции.

Источник: Jack Daniels "Daniels' Running Formula"
"""
from typing import Dict, Optional, Tuple
from ..utils.logger import logger


# Таблица VDOT: время в секундах для каждой дистанции
# Формат: VDOT -> {distance: time_seconds}
VDOT_TABLE = {
    30: {'5k': 1860, '10k': 3900, 'half': 8700, 'marathon': 18300},
    31: {'5k': 1800, '10k': 3780, 'half': 8430, 'marathon': 17760},
    32: {'5k': 1746, '10k': 3660, 'half': 8166, 'marathon': 17220},
    33: {'5k': 1692, '10k': 3546, 'half': 7920, 'marathon': 16716},
    34: {'5k': 1644, '10k': 3438, 'half': 7686, 'marathon': 16224},
    35: {'5k': 1596, '10k': 3336, 'half': 7464, 'marathon': 15756},
    36: {'5k': 1554, '10k': 3240, 'half': 7254, 'marathon': 15312},
    37: {'5k': 1512, '10k': 3150, 'half': 7056, 'marathon': 14886},
    38: {'5k': 1470, '10k': 3066, 'half': 6864, 'marathon': 14478},
    39: {'5k': 1434, '10k': 2982, 'half': 6684, 'marathon': 14094},
    40: {'5k': 1398, '10k': 2904, 'half': 6516, 'marathon': 13728},
    41: {'5k': 1362, '10k': 2832, 'half': 6354, 'marathon': 13380},
    42: {'5k': 1332, '10k': 2760, 'half': 6198, 'marathon': 13050},
    43: {'5k': 1302, '10k': 2694, 'half': 6054, 'marathon': 12738},
    44: {'5k': 1272, '10k': 2628, 'half': 5916, 'marathon': 12438},
    45: {'5k': 1242, '10k': 2568, 'half': 5784, 'marathon': 12156},
    46: {'5k': 1218, '10k': 2508, 'half': 5658, 'marathon': 11886},
    47: {'5k': 1194, '10k': 2454, 'half': 5538, 'marathon': 11634},
    48: {'5k': 1170, '10k': 2400, 'half': 5424, 'marathon': 11394},
    49: {'5k': 1146, '10k': 2352, 'half': 5316, 'marathon': 11166},
    50: {'5k': 1128, '10k': 2304, 'half': 5214, 'marathon': 10950},
    51: {'5k': 1104, '10k': 2256, 'half': 5112, 'marathon': 10746},
    52: {'5k': 1086, '10k': 2214, 'half': 5016, 'marathon': 10554},
    53: {'5k': 1068, '10k': 2172, 'half': 4926, 'marathon': 10368},
    54: {'5k': 1050, '10k': 2130, 'half': 4836, 'marathon': 10194},
    55: {'5k': 1032, '10k': 2094, 'half': 4752, 'marathon': 10026},
    56: {'5k': 1020, '10k': 2058, 'half': 4674, 'marathon': 9870},
    57: {'5k': 1002, '10k': 2022, 'half': 4596, 'marathon': 9720},
    58: {'5k': 990, '10k': 1992, 'half': 4524, 'marathon': 9576},
    59: {'5k': 972, '10k': 1956, 'half': 4452, 'marathon': 9438},
    60: {'5k': 960, '10k': 1926, 'half': 4386, 'marathon': 9306},
    61: {'5k': 948, '10k': 1896, 'half': 4320, 'marathon': 9180},
    62: {'5k': 936, '10k': 1866, 'half': 4254, 'marathon': 9060},
    63: {'5k': 924, '10k': 1842, 'half': 4194, 'marathon': 8946},
    64: {'5k': 912, '10k': 1812, 'half': 4134, 'marathon': 8832},
    65: {'5k': 900, '10k': 1788, 'half': 4080, 'marathon': 8724},
    66: {'5k': 894, '10k': 1764, 'half': 4026, 'marathon': 8622},
    67: {'5k': 882, '10k': 1740, 'half': 3972, 'marathon': 8520},
    68: {'5k': 870, '10k': 1716, 'half': 3924, 'marathon': 8424},
    69: {'5k': 864, '10k': 1698, 'half': 3876, 'marathon': 8328},
    70: {'5k': 852, '10k': 1674, 'half': 3828, 'marathon': 8238},
}

# Тренировочные темпы по VDOT (сек/км)
# E = Easy, M = Marathon, T = Threshold, I = Interval, R = Repetition
TRAINING_PACES = {
    30: {'E': 444, 'M': 396, 'T': 366, 'I': 330, 'R': 306},
    32: {'E': 426, 'M': 378, 'T': 354, 'I': 318, 'R': 294},
    34: {'E': 408, 'M': 366, 'T': 342, 'I': 306, 'R': 282},
    36: {'E': 396, 'M': 354, 'T': 330, 'I': 294, 'R': 270},
    38: {'E': 384, 'M': 342, 'T': 318, 'I': 282, 'R': 258},
    40: {'E': 372, 'M': 330, 'T': 306, 'I': 270, 'R': 246},
    42: {'E': 360, 'M': 318, 'T': 294, 'I': 258, 'R': 234},
    44: {'E': 348, 'M': 306, 'T': 282, 'I': 246, 'R': 222},
    46: {'E': 336, 'M': 294, 'T': 270, 'I': 234, 'R': 210},
    48: {'E': 324, 'M': 282, 'T': 258, 'I': 222, 'R': 198},
    50: {'E': 318, 'M': 276, 'T': 252, 'I': 216, 'R': 192},
    52: {'E': 306, 'M': 264, 'T': 240, 'I': 204, 'R': 180},
    54: {'E': 300, 'M': 258, 'T': 234, 'I': 198, 'R': 174},
    56: {'E': 294, 'M': 252, 'T': 228, 'I': 192, 'R': 168},
    58: {'E': 288, 'M': 246, 'T': 222, 'I': 186, 'R': 162},
    60: {'E': 282, 'M': 240, 'T': 216, 'I': 180, 'R': 156},
    62: {'E': 276, 'M': 234, 'T': 210, 'I': 174, 'R': 150},
    64: {'E': 270, 'M': 228, 'T': 204, 'I': 168, 'R': 144},
    66: {'E': 264, 'M': 222, 'T': 198, 'I': 162, 'R': 138},
    68: {'E': 258, 'M': 216, 'T': 192, 'I': 156, 'R': 132},
    70: {'E': 252, 'M': 210, 'T': 186, 'I': 150, 'R': 126},
}


def calculate_vdot_from_time(distance: str, time_seconds: int) -> Optional[float]:
    """
    Рассчитать VDOT по результату на дистанции

    Args:
        distance: Дистанция ("5k", "10k", "half", "marathon")
        time_seconds: Время в секундах

    Returns:
        VDOT или None если не удалось рассчитать
    """
    if distance not in ['5k', '10k', 'half', 'marathon']:
        logger.warning(f"Неизвестная дистанция: {distance}")
        return None

    # Находим ближайший VDOT по таблице
    best_vdot = None
    best_diff = float('inf')

    for vdot, times in VDOT_TABLE.items():
        if distance in times:
            diff = abs(times[distance] - time_seconds)
            if diff < best_diff:
                best_diff = diff
                best_vdot = vdot

    if best_vdot is None:
        return None

    # Интерполяция для более точного значения
    # Если время между двумя VDOT, интерполируем
    vdot_list = sorted(VDOT_TABLE.keys())
    for i, v in enumerate(vdot_list[:-1]):
        v_next = vdot_list[i + 1]
        t1 = VDOT_TABLE[v][distance]
        t2 = VDOT_TABLE[v_next][distance]

        if t2 <= time_seconds <= t1:
            # Линейная интерполяция
            ratio = (t1 - time_seconds) / (t1 - t2)
            interpolated = v + ratio * (v_next - v)
            logger.info(f"VDOT рассчитан: {interpolated:.1f} (по {distance} за {format_time(time_seconds)})")
            return round(interpolated, 1)

    logger.info(f"VDOT рассчитан: {best_vdot} (по {distance} за {format_time(time_seconds)})")
    return float(best_vdot)


def calculate_best_vdot(personal_records: Dict[str, Dict]) -> Tuple[Optional[float], Optional[str], Optional[int]]:
    """
    Рассчитать лучший VDOT из всех персональных рекордов

    Args:
        personal_records: {"5k": {"time_seconds": 1500}, "10k": {...}, ...}

    Returns:
        Tuple (vdot, source_distance, time_seconds) или (None, None, None)
    """
    best_vdot = None
    best_source = None
    best_time = None

    for distance, data in personal_records.items():
        time_seconds = data.get('time_seconds')
        if time_seconds:
            vdot = calculate_vdot_from_time(distance, time_seconds)
            if vdot and (best_vdot is None or vdot > best_vdot):
                best_vdot = vdot
                best_source = distance
                best_time = time_seconds

    if best_vdot:
        logger.info(f"Лучший VDOT: {best_vdot} (по {best_source})")

    return best_vdot, best_source, best_time


def get_training_paces(vdot: float) -> Dict[str, str]:
    """
    Получить тренировочные темпы по VDOT

    Args:
        vdot: Значение VDOT

    Returns:
        Словарь темпов: {"easy": "5:30", "marathon": "4:45", ...}
    """
    # Находим ближайший VDOT с темпами
    vdot_keys = sorted(TRAINING_PACES.keys())
    closest_vdot = min(vdot_keys, key=lambda x: abs(x - vdot))

    # Интерполяция между двумя ближайшими значениями
    if vdot > closest_vdot and closest_vdot < max(vdot_keys):
        v1 = closest_vdot
        v2 = vdot_keys[vdot_keys.index(closest_vdot) + 1]
    elif vdot < closest_vdot and closest_vdot > min(vdot_keys):
        v1 = vdot_keys[vdot_keys.index(closest_vdot) - 1]
        v2 = closest_vdot
    else:
        # Используем точное значение
        paces = TRAINING_PACES[closest_vdot]
        return {
            'easy': format_pace(paces['E']),
            'easy_range': f"{format_pace(paces['E'])} - {format_pace(int(paces['E'] * 1.1))}",
            'marathon': format_pace(paces['M']),
            'threshold': format_pace(paces['T']),
            'interval': format_pace(paces['I']),
            'repetition': format_pace(paces['R']),
        }

    # Интерполяция
    ratio = (vdot - v1) / (v2 - v1)
    paces = {}
    for pace_type in ['E', 'M', 'T', 'I', 'R']:
        p1 = TRAINING_PACES[v1][pace_type]
        p2 = TRAINING_PACES[v2][pace_type]
        interpolated = int(p1 + ratio * (p2 - p1))
        paces[pace_type] = interpolated

    return {
        'easy': format_pace(paces['E']),
        'easy_range': f"{format_pace(paces['E'])} - {format_pace(int(paces['E'] * 1.1))}",
        'marathon': format_pace(paces['M']),
        'threshold': format_pace(paces['T']),
        'interval': format_pace(paces['I']),
        'repetition': format_pace(paces['R']),
    }


def get_training_paces_seconds(vdot: float) -> Dict[str, int]:
    """
    Получить тренировочные темпы в секундах на км

    Args:
        vdot: Значение VDOT

    Returns:
        Словарь темпов в секундах: {"easy": 330, "marathon": 285, ...}
    """
    vdot_keys = sorted(TRAINING_PACES.keys())
    closest_vdot = min(vdot_keys, key=lambda x: abs(x - vdot))

    # Интерполяция
    if vdot > closest_vdot and closest_vdot < max(vdot_keys):
        v1 = closest_vdot
        v2 = vdot_keys[vdot_keys.index(closest_vdot) + 1]
        ratio = (vdot - v1) / (v2 - v1)
    elif vdot < closest_vdot and closest_vdot > min(vdot_keys):
        v1 = vdot_keys[vdot_keys.index(closest_vdot) - 1]
        v2 = closest_vdot
        ratio = (vdot - v1) / (v2 - v1)
    else:
        paces = TRAINING_PACES[closest_vdot]
        return {
            'easy': paces['E'],
            'marathon': paces['M'],
            'threshold': paces['T'],
            'interval': paces['I'],
            'repetition': paces['R'],
        }

    paces = {}
    for pace_type, name in [('E', 'easy'), ('M', 'marathon'), ('T', 'threshold'), ('I', 'interval'), ('R', 'repetition')]:
        p1 = TRAINING_PACES[v1][pace_type]
        p2 = TRAINING_PACES[v2][pace_type]
        paces[name] = int(p1 + ratio * (p2 - p1))

    return paces


def format_pace(seconds_per_km: int) -> str:
    """Форматирование темпа в mm:ss"""
    minutes = seconds_per_km // 60
    seconds = seconds_per_km % 60
    return f"{minutes}:{seconds:02d}"


def format_time(seconds: int) -> str:
    """Форматирование времени в hh:mm:ss или mm:ss"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def get_predicted_times(vdot: float) -> Dict[str, str]:
    """
    Получить прогнозируемые времена на дистанциях по VDOT

    Args:
        vdot: Значение VDOT

    Returns:
        Словарь прогнозов: {"5k": "22:30", "10k": "46:45", ...}
    """
    vdot_int = int(round(vdot))
    if vdot_int not in VDOT_TABLE:
        # Ищем ближайший
        vdot_int = min(VDOT_TABLE.keys(), key=lambda x: abs(x - vdot))

    times = VDOT_TABLE[vdot_int]
    return {
        '5k': format_time(times['5k']),
        '10k': format_time(times['10k']),
        'half': format_time(times['half']),
        'marathon': format_time(times['marathon']),
    }


def format_vdot_summary(vdot: float, source: str, time_seconds: int) -> str:
    """
    Форматирование саммари VDOT для пользователя

    Args:
        vdot: Значение VDOT
        source: Источник ("5k", "10k", "half", "marathon")
        time_seconds: Время результата

    Returns:
        Текст для отображения пользователю
    """
    distance_names = {
        '5k': '5 км',
        '10k': '10 км',
        'half': 'полумарафон',
        'marathon': 'марафон'
    }

    paces = get_training_paces(vdot)

    summary = (
        f"**Твой VDOT: {vdot:.0f}**\n"
        f"(рассчитан по результату {distance_names.get(source, source)} за {format_time(time_seconds)})\n\n"
        f"**Тренировочные темпы (Jack Daniels):**\n"
        f"- Easy (лёгкий): {paces['easy_range']}/км\n"
        f"- Marathon (марафонский): {paces['marathon']}/км\n"
        f"- Threshold (темповый): {paces['threshold']}/км\n"
        f"- Interval (интервальный): {paces['interval']}/км\n"
        f"- Repetition (ускорения): {paces['repetition']}/км"
    )

    return summary
