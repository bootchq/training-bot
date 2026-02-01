"""Автоопределение уровня подготовки по данным Garmin"""
from datetime import timedelta
from typing import Optional, Tuple

from sqlalchemy import func

from ..database.db import db, Training
from ..utils import time_utils
from ..utils.logger import logger
from .vdot_calculator import find_best_times_from_trainings, calculate_vdot_from_time


def detect_fitness_level(user_id: int) -> Tuple[Optional[str], dict]:
    """
    Определяет уровень подготовки пользователя по истории тренировок.

    Анализирует:
    - Максимальную дистанцию (>20 км = не новичок)
    - VDOT из лучших результатов на 10 км и полумарафоне
    - Темп на длинных тренировках (15+ км)
    - Недельный объём и частоту тренировок

    Args:
        user_id: ID пользователя

    Returns:
        Tuple[level, stats]:
        - level: "beginner" / "intermediate" / "advanced" / None (если мало данных)
        - stats: словарь с метриками для объяснения пользователю
    """
    today = time_utils.today()
    four_weeks_ago = today - timedelta(days=28)

    with db.get_session() as session:
        # Запрос 1: общая статистика
        stats_query = session.query(
            func.min(Training.date).label('first_date'),
            func.max(Training.date).label('last_date'),
            func.count(Training.id).label('total_count'),
            func.max(Training.distance_km).label('max_distance')
        ).filter(
            Training.user_id == user_id,
            Training.type == 'actual'
        ).first()

        if not stats_query or not stats_query.total_count or stats_query.total_count < 4:
            count = stats_query.total_count if stats_query else 0
            logger.info(f"User {user_id}: недостаточно тренировок ({count})")
            return None, {"reason": "insufficient_data", "trainings_count": count or 0}

        first_date = stats_query.first_date
        last_date = stats_query.last_date
        total_count = stats_query.total_count
        max_distance = stats_query.max_distance or 0

        # Запрос 2: статистика за последние 4 недели
        recent_stats = session.query(
            func.count(Training.id).label('count'),
            func.sum(Training.distance_km).label('distance')
        ).filter(
            Training.user_id == user_id,
            Training.type == 'actual',
            Training.date >= four_weeks_ago
        ).first()

        recent_count = recent_stats.count or 0
        recent_distance = recent_stats.distance or 0

        # Запрос 3: лучший темп на длинных тренировках (15+ км)
        long_runs = session.query(
            Training.distance_km,
            Training.duration_min
        ).filter(
            Training.user_id == user_id,
            Training.type == 'actual',
            Training.distance_km >= 15,
            Training.duration_min.isnot(None),
            Training.duration_min > 0
        ).all()

    # Расчёт недельных метрик
    if recent_count >= 2:
        weekly_trainings = recent_count / 4
        weekly_distance = recent_distance / 4
    else:
        # Fallback: используем общие данные
        total_weeks = max(1, (last_date - first_date).days // 7)
        weekly_trainings = total_count / total_weeks
        weekly_distance = 0

    # Лучший темп на длинных
    best_long_run_pace = None
    if long_runs:
        paces = []
        for t in long_runs:
            if t.duration_min and t.distance_km:
                pace_sec = (t.duration_min * 60) / t.distance_km
                paces.append(pace_sec)
        if paces:
            best_long_run_pace = min(paces)

    # VDOT из обычных тренировок
    best_times = find_best_times_from_trainings(user_id)
    vdot = None
    vdot_source = None

    # Выбираем лучший VDOT (10k обычно точнее)
    if '10k' in best_times:
        vdot_10k = calculate_vdot_from_time('10k', best_times['10k']['time_seconds'])
        if vdot_10k:
            vdot = vdot_10k
            vdot_source = '10k'

    if 'half' in best_times:
        vdot_half = calculate_vdot_from_time('half', best_times['half']['time_seconds'])
        if vdot_half and (vdot is None or vdot_half > vdot):
            vdot = vdot_half
            vdot_source = 'half'

    # Период данных (не стаж — это разные вещи)
    data_period_days = (last_date - first_date).days

    # Собираем статистику
    stats = {
        "max_distance_km": round(max_distance, 1),
        "weekly_distance_km": round(weekly_distance, 1),
        "weekly_trainings": round(weekly_trainings, 1),
        "total_trainings": total_count,
        "data_period_days": data_period_days,
        "vdot": round(vdot, 1) if vdot else None,
        "vdot_source": vdot_source,
        "best_long_run_pace_sec": int(best_long_run_pace) if best_long_run_pace else None
    }

    # Определяем уровень
    level = _calculate_level(
        max_distance_km=max_distance,
        weekly_km=weekly_distance,
        weekly_trainings=weekly_trainings,
        vdot=vdot,
        long_run_pace_sec=best_long_run_pace
    )
    stats["level"] = level

    # Логирование
    pace_str = _format_pace(int(best_long_run_pace)) if best_long_run_pace else "N/A"
    logger.info(
        f"User {user_id}: уровень {level} "
        f"(max {max_distance:.1f} км, VDOT {vdot or 'N/A'}, "
        f"темп длинных {pace_str}, "
        f"{weekly_distance:.1f} км/нед)"
    )

    return level, stats


def _calculate_level(
    max_distance_km: float,
    weekly_km: float,
    weekly_trainings: float,
    vdot: Optional[float],
    long_run_pace_sec: Optional[float]
) -> str:
    """
    Определяет уровень на основе метрик.

    Логика (приоритет сверху вниз):
    1. VDOT >= 50 → advanced
    2. max_distance >= 30 км → advanced
    3. VDOT >= 40 → intermediate
    4. max_distance >= 20 км → intermediate
    5. Длинная 15+ км с темпом < 7:00/км → intermediate
    6. weekly_km >= 40 и weekly_trainings >= 4 → intermediate
    7. Иначе → beginner

    Args:
        max_distance_km: Максимальная дистанция за всю историю
        weekly_km: Средний недельный объём (км)
        weekly_trainings: Среднее количество тренировок в неделю
        vdot: Расчётный VDOT (или None)
        long_run_pace_sec: Лучший темп на длинной 15+ км (сек/км) или None
    """
    # Advanced сигналы
    if vdot and vdot >= 50:
        return "advanced"

    if max_distance_km >= 30:
        return "advanced"

    # Intermediate сигналы
    if vdot and vdot >= 40:
        return "intermediate"

    if max_distance_km >= 20:
        return "intermediate"

    # Темп < 7:00/км (420 сек) на длинной = не новичок
    if long_run_pace_sec and long_run_pace_sec < 420:
        return "intermediate"

    # Хороший объём и частота
    if weekly_km >= 40 and weekly_trainings >= 4:
        return "intermediate"

    return "beginner"


def _format_pace(seconds_per_km: int) -> str:
    """Форматирование темпа в mm:ss"""
    minutes = seconds_per_km // 60
    seconds = seconds_per_km % 60
    return f"{minutes}:{seconds:02d}"


def format_level_explanation(level: str, stats: dict) -> str:
    """Форматирует объяснение определённого уровня для пользователя"""
    level_names = {
        "beginner": "🟢 Новичок",
        "intermediate": "🟡 Средний",
        "advanced": "🔴 Опытный"
    }

    level_name = level_names.get(level, level)

    text = "📊 Анализ твоих тренировок из Garmin:\n\n"

    # Максимальная дистанция
    max_dist = stats.get('max_distance_km')
    if max_dist:
        text += f"• Макс. дистанция: {max_dist} км\n"

    # VDOT
    vdot = stats.get('vdot')
    vdot_source = stats.get('vdot_source')
    if vdot:
        source_names = {'10k': '10 км', 'half': 'полумарафон'}
        source_name = source_names.get(vdot_source, vdot_source)
        text += f"• VDOT: {vdot} (по {source_name})\n"

    # Темп на длинных
    pace_sec = stats.get('best_long_run_pace_sec')
    if pace_sec:
        text += f"• Темп на длинных: {_format_pace(pace_sec)}/км\n"

    # Недельные метрики
    weekly_km = stats.get('weekly_distance_km')
    weekly_tr = stats.get('weekly_trainings')
    if weekly_km:
        text += f"• Объём: ~{weekly_km} км/нед\n"
    if weekly_tr:
        text += f"• Тренировок: ~{weekly_tr}/нед\n"

    text += f"\n✅ Твой уровень: **{level_name}**"

    return text
