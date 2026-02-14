"""
Калькулятор VDOT по методологии Jack Daniels

=== ФОРМУЛЫ DANIELS ===
VO2 = -4.60 + 0.182258*v + 0.000104*v²  (v = скорость м/мин)
F(t) = 0.8 + 0.1894393*e^(-0.012778*t) + 0.2989558*e^(-0.1932605*t)
VDOT = VO2 / F(t)

Источник: Jack Daniels "Daniels' Running Formula" (4th ed, 2021)
Формулы позволяют рассчитать VDOT для ЛЮБОЙ дистанции, не только стандартных.

=== 5 ЗОН ТЕМПОВ ===
- E (Easy): 65-79% VO2max — восстановление, длительные, аэробная база
- M (Marathon): целевой темп марафона — специфичность
- T (Threshold): "комфортно тяжело" — развитие порога, ~60 мин удержания
- I (Interval): 97-100% VO2max — 3-5 мин интервалы, развитие VO2max
- R (Repetition): быстрее 5k — нейромышечная работа, экономичность
"""
import math
from typing import Any, Dict, Optional, Tuple


from ..database.db import db, Training
from ..utils.logger import logger

# Дистанции в метрах — поддерживаются формулами Daniels
DISTANCES = {
    '800': 800,
    '1500': 1500,
    'mile': 1609.34,
    '3k': 3000,
    '5k': 5000,
    '8k': 8000,
    '10k': 10000,
    '15k': 15000,
    'half': 21097.5,
    'marathon': 42195,
}

# Тренировочные темпы по VDOT (сек/км) — из таблиц Daniels (4th ed)
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


# === Формулы Jack Daniels (Daniels' Running Formula, 4th ed) ===

def _vo2_demand(velocity: float) -> float:
    """VO2 (мл/кг/мин) при скорости v (м/мин)"""
    return -4.60 + 0.182258 * velocity + 0.000104 * velocity ** 2


def _vo2max_fraction(time_minutes: float) -> float:
    """Доля VO2max, удерживаемая t минут при максимальном усилии"""
    t = time_minutes
    return (0.8 + 0.1894393 * math.exp(-0.012778 * t)
            + 0.2989558 * math.exp(-0.1932605 * t))


def _velocity_from_vo2(vo2: float) -> float:
    """Скорость (м/мин) по VO2 — обратная квадратичная формула"""
    a = 0.000104
    b = 0.182258
    c = -4.60 - vo2
    disc = b ** 2 - 4 * a * c
    if disc < 0:
        return 0.0
    return (-b + math.sqrt(disc)) / (2 * a)


def _predict_time_seconds(vdot: float, distance_meters: float) -> int:
    """Прогноз времени (сек) для дистанции по VDOT — метод бисекции"""
    lo, hi = 2.0, 600.0  # от 2 мин до 10 часов
    for _ in range(100):
        mid = (lo + hi) / 2
        v = distance_meters / mid
        vo2 = _vo2_demand(v)
        f = _vo2max_fraction(mid)
        computed = vo2 / f
        if computed > vdot:
            lo = mid  # слишком быстро → увеличить время
        else:
            hi = mid
        if hi - lo < 0.005:
            break
    return int(round((lo + hi) / 2 * 60))


def calculate_vdot_from_time(distance: str, time_seconds: int,
                             is_race: bool = False) -> Optional[float]:
    """
    Рассчитать VDOT по результату на дистанции (формулы Daniels)

    Поддерживает любую дистанцию из DISTANCES (800м — марафон).
    Тренировочные результаты корректируются на 3% (race equivalent).

    Args:
        distance: Дистанция ("5k", "10k", "half", "marathon", "3k", "1500" и др.)
        time_seconds: Время в секундах
        is_race: True если результат с забега (макс. усилие)

    Returns:
        VDOT или None если неизвестная дистанция
    """
    # Коррекция: тренировочный бег → на 3% медленнее забега
    if not is_race:
        time_seconds = int(time_seconds * 0.97)

    dist_meters = DISTANCES.get(distance)
    if dist_meters is None:
        logger.warning(f"Неизвестная дистанция: {distance}")
        return None

    time_minutes = time_seconds / 60.0
    velocity = dist_meters / time_minutes  # м/мин

    vo2 = _vo2_demand(velocity)
    fraction = _vo2max_fraction(time_minutes)
    vdot = vo2 / fraction

    logger.info(f"VDOT = {vdot:.1f} (по {distance} за {format_time(time_seconds)})")
    return round(vdot, 1)


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
    Прогнозируемые времена на дистанциях по VDOT (формулы Daniels)

    Работает для любого VDOT (не ограничен диапазоном 30-70).

    Args:
        vdot: Значение VDOT

    Returns:
        Словарь прогнозов: {"5k": "22:30", "10k": "46:45", ...}
    """
    predict_distances = {
        '1500': 1500,
        '3k': 3000,
        '5k': 5000,
        '10k': 10000,
        'half': 21097.5,
        'marathon': 42195,
    }
    result = {}
    for name, meters in predict_distances.items():
        t = _predict_time_seconds(vdot, meters)
        result[name] = format_time(t)
    return result


def find_best_times_from_trainings(user_id: int) -> Dict[str, Dict[str, Any]]:
    """
    Найти лучшие времена на дистанциях из истории тренировок в БД.

    Ищет обычные тренировки (не только официальные PR):
    - 5 км: тренировки 4.5-5.5 км
    - 10 км: тренировки 8.0-11.0 км (включая близкие дистанции)
    - Полумарафон: тренировки 18.0-23.0 км (включая длинные)

    Логика:
    - Для тренировок в диапазоне - нормализует время к целевой дистанции
    - Для длинных (>10 км) - использует как источник для 10k (берет темп первых 10 км)

    Args:
        user_id: ID пользователя

    Returns:
        {"10k": {"time_seconds": 3420, "distance_km": 10.2, "date": ...}, ...}
    """
    records = {}

    # Диапазоны дистанций для поиска (расширенные для гибкости)
    distance_ranges = {
        '3k': (2.5, 3.5),
        '5k': (4.5, 5.5),
        '10k': (8.0, 11.0),
        'half': (18.0, 23.0),
    }

    with db.get_session() as session:
        for dist_key, (min_km, max_km) in distance_ranges.items():
            # Ищем тренировки в диапазоне дистанции с валидным временем
            trainings = session.query(
                Training.distance_km,
                Training.duration_min,
                Training.date
            ).filter(
                Training.user_id == user_id,
                Training.type == 'actual',
                Training.distance_km >= min_km,
                Training.distance_km <= max_km,
                Training.duration_min.isnot(None),
                Training.duration_min > 0
            ).all()

            if not trainings:
                continue

            # Находим лучшее время (нормализуем к точной дистанции)
            best_time = None
            best_training = None

            for t in trainings:
                # Время в секундах
                time_sec = t.duration_min * 60

                # Нормализуем к точной дистанции
                target_map = {'3k': 3.0, '5k': 5.0, '10k': 10.0, 'half': 21.1}
                target_km = target_map[dist_key]

                normalized_time = (time_sec / t.distance_km) * target_km

                if best_time is None or normalized_time < best_time:
                    best_time = normalized_time
                    best_training = t

            if best_training:
                records[dist_key] = {
                    'time_seconds': int(best_time),
                    'distance_km': best_training.distance_km,
                    'date': best_training.date
                }
                logger.info(
                    f"User {user_id}: лучшее время {dist_key} = "
                    f"{format_time(int(best_time))} "
                    f"(из тренировки {best_training.distance_km:.1f} км)"
                )

    return records


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
        '1500': '1500 м',
        '3k': '3 км',
        '5k': '5 км',
        '10k': '10 км',
        'half': 'полумарафон',
        'marathon': 'марафон'
    }

    paces = get_training_paces(vdot)
    predictions = get_predicted_times(vdot)

    summary = (
        f"**Твой VDOT: {vdot:.0f}**\n"
        f"(рассчитан по результату {distance_names.get(source, source)} за {format_time(time_seconds)})\n\n"
        f"**Прогнозы на дистанциях:**\n"
        f"- 5 км: {predictions['5k']}\n"
        f"- 10 км: {predictions['10k']}\n"
        f"- Полумарафон: {predictions['half']}\n"
        f"- Марафон: {predictions['marathon']}\n\n"
        f"**Тренировочные темпы (Jack Daniels):**\n"
        f"- Easy (лёгкий): {paces['easy_range']}/км\n"
        f"- Marathon (марафонский): {paces['marathon']}/км\n"
        f"- Threshold (темповый): {paces['threshold']}/км\n"
        f"- Interval (интервальный): {paces['interval']}/км\n"
        f"- Repetition (ускорения): {paces['repetition']}/км"
    )

    return summary
