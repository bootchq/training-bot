"""Автоопределение уровня подготовки по данным Garmin"""
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func

from ..database.db import db, Training
from ..utils import time_utils
from ..utils.logger import logger
from .vdot_calculator import find_best_times_from_trainings, calculate_vdot_from_time, format_time


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

    # VDOT из обычных тренировок с time decay
    best_times = find_best_times_from_trainings(user_id)
    vdot = None
    vdot_source = None

    # Выбираем лучший VDOT с учётом свежести (приоритет: 10k > half > 5k > 3k)
    for dist_key in ['10k', 'half', '5k', '3k']:
        if dist_key not in best_times:
            continue
        bt = best_times[dist_key]
        raw_vdot = calculate_vdot_from_time(dist_key, bt['time_seconds'])
        if not raw_vdot:
            continue

        # Time decay: свежие результаты важнее
        days_ago = (today - bt['date']).days if bt.get('date') else 0
        decay = _time_decay(days_ago)
        adjusted_vdot = raw_vdot * decay

        if vdot is None or adjusted_vdot > vdot:
            vdot = adjusted_vdot
            vdot_source = dist_key

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

    # Сохраняем VDOT в базу если рассчитан
    if vdot and vdot_source:
        db.save_user_physiology(
            user_id,
            vdot=vdot,
            vdot_source=vdot_source,
            vdot_time_seconds=best_times.get(vdot_source, {}).get('time_seconds')
        )
        logger.info(f"VDOT {vdot:.1f} сохранён в базу для user_id={user_id}")

    return level, stats


def _calculate_level(
    max_distance_km: float,
    weekly_km: float,
    weekly_trainings: float,
    vdot: Optional[float],
    long_run_pace_sec: Optional[float]
) -> str:
    """
    Определяет уровень через скоринговую систему (вместо каскада if/else).

    Каждая метрика даёт 0-100 очков, взвешенных по важности:
    - VDOT: 40% (главный показатель физ. формы)
    - Недельный объём: 20%
    - Макс. дистанция: 15%
    - Темп на длинных: 15%
    - Регулярность: 10%

    Итоговый балл → уровень:
    - 0-25: beginner
    - 26-55: intermediate
    - 56+: advanced
    """
    score = 0.0

    # 1. VDOT (0-40 баллов) — главный индикатор
    if vdot:
        score += _score_metric(vdot, thresholds=[
            (30, 0), (35, 10), (40, 20), (45, 30), (50, 40)
        ])

    # 2. Недельный объём (0-20 баллов)
    score += _score_metric(weekly_km, thresholds=[
        (10, 0), (20, 5), (40, 12), (60, 18), (80, 20)
    ])

    # 3. Макс. дистанция (0-15 баллов)
    score += _score_metric(max_distance_km, thresholds=[
        (10, 0), (15, 5), (21, 9), (30, 13), (42, 15)
    ])

    # 4. Темп на длинных (0-15 баллов) — инвертированный (быстрее = лучше)
    if long_run_pace_sec:
        # Конвертируем: 450 сек/км = 0 баллов, 300 сек/км = 15 баллов
        score += _score_metric(450 - long_run_pace_sec, thresholds=[
            (0, 0), (30, 4), (90, 9), (120, 13), (150, 15)
        ])

    # 5. Регулярность (0-10 баллов)
    score += _score_metric(weekly_trainings, thresholds=[
        (2, 0), (3, 3), (4, 6), (5, 9), (6, 10)
    ])

    # Итоговый уровень
    if score >= 56:
        return "advanced"
    elif score >= 26:
        return "intermediate"
    return "beginner"


def _score_metric(value: float, thresholds: List[Tuple[float, float]]) -> float:
    """
    Линейная интерполяция баллов по порогам.

    Args:
        value: Значение метрики
        thresholds: [(порог, баллы), ...] — отсортировано по возрастанию

    Returns:
        Баллы (с плавной интерполяцией между порогами)
    """
    if value <= thresholds[0][0]:
        return thresholds[0][1]

    for i in range(len(thresholds) - 1):
        t1, s1 = thresholds[i]
        t2, s2 = thresholds[i + 1]
        if t1 <= value <= t2:
            ratio = (value - t1) / (t2 - t1)
            return s1 + ratio * (s2 - s1)

    return thresholds[-1][1]


def _time_decay(days_ago: int) -> float:
    """
    Коэффициент свежести результата.

    - 0-28 дней (4 недели): 1.0 (полный вес)
    - 29-84 дня (5-12 недель): 0.95 (небольшое снижение)
    - 85+ дней (12+ недель): 0.85 (результат устарел)
    """
    if days_ago <= 28:
        return 1.0
    elif days_ago <= 84:
        return 0.95
    return 0.85


def _format_pace(seconds_per_km: int) -> str:
    """Форматирование темпа в mm:ss"""
    minutes = seconds_per_km // 60
    seconds = seconds_per_km % 60
    return f"{minutes}:{seconds:02d}"


def get_level_evidence(user_id: int) -> Dict[str, Any]:
    """
    Собирает доказательства (конкретные тренировки), повлиявшие на определение уровня.

    Returns:
        {
            "evidence": [
                {"type": "vdot_10k", "date": "2026-01-15", "distance_km": 10.2,
                 "time": "57:00", "result": "VDOT 33.7", "signal": "intermediate"},
                ...
            ],
            "missing": ["Нет тренировок 10+ км для расчёта VDOT"],
            "has_sufficient_data": True/False
        }
    """
    evidence = []
    missing = []

    with db.get_session() as session:
        # 1. Найти тренировку с максимальной дистанцией
        max_dist_training = session.query(Training).filter(
            Training.user_id == user_id,
            Training.type == 'actual',
            Training.distance_km.isnot(None)
        ).order_by(Training.distance_km.desc()).first()

        if max_dist_training and max_dist_training.distance_km:
            dist = max_dist_training.distance_km
            signal = "advanced" if dist >= 30 else ("intermediate" if dist >= 20 else "beginner")

            # Рассчитываем темп
            pace_str = None
            if max_dist_training.duration_min and dist > 0:
                pace_sec = (max_dist_training.duration_min * 60) / dist
                pace_str = _format_pace(int(pace_sec))

            evidence.append({
                "type": "max_distance",
                "date": max_dist_training.date.strftime("%d.%m.%Y") if max_dist_training.date else None,
                "distance_km": round(dist, 1),
                "time": f"{max_dist_training.duration_min} мин" if max_dist_training.duration_min else None,
                "pace": pace_str,
                "result": f"{dist:.1f} км",
                "signal": signal,
                "explanation": f"≥20 км → intermediate, ≥30 км → advanced"
            })
        else:
            missing.append("Нет записанных тренировок")

        # 2. Найти лучшие результаты на 10к и полумарафоне для VDOT
        best_times = find_best_times_from_trainings(user_id)

        if '10k' in best_times:
            bt = best_times['10k']
            vdot = calculate_vdot_from_time('10k', bt['time_seconds'])
            signal = "advanced" if vdot and vdot >= 50 else ("intermediate" if vdot and vdot >= 40 else "beginner")

            evidence.append({
                "type": "vdot_10k",
                "date": bt['date'].strftime("%d.%m.%Y") if bt.get('date') else None,
                "distance_km": round(bt.get('distance_km', 10), 1),
                "time": format_time(bt['time_seconds']),
                "result": f"VDOT {vdot:.1f}" if vdot else "N/A",
                "signal": signal,
                "explanation": f"VDOT ≥40 → intermediate, ≥50 → advanced"
            })
        else:
            # Проверяем есть ли тренировки в расширенном диапазоне (8-11 км)
            near_10k = session.query(Training).filter(
                Training.user_id == user_id,
                Training.type == 'actual',
                Training.distance_km >= 8,
                Training.distance_km <= 11,
                Training.duration_min.isnot(None),
                Training.duration_min > 0
            ).count()
            if near_10k > 0:
                missing.append(f"Нет тренировок 8-11 км с корректным временем для расчёта VDOT")
            else:
                missing.append("Нет тренировок 8-11 км для расчёта VDOT (пробеги больше 8 км)")

        if 'half' in best_times:
            bt = best_times['half']
            vdot = calculate_vdot_from_time('half', bt['time_seconds'])
            signal = "advanced" if vdot and vdot >= 50 else ("intermediate" if vdot and vdot >= 40 else "beginner")

            evidence.append({
                "type": "vdot_half",
                "date": bt['date'].strftime("%d.%m.%Y") if bt.get('date') else None,
                "distance_km": round(bt.get('distance_km', 21.1), 1),
                "time": format_time(bt['time_seconds']),
                "result": f"VDOT {vdot:.1f}" if vdot else "N/A",
                "signal": signal,
                "explanation": f"VDOT ≥40 → intermediate, ≥50 → advanced"
            })

        # 3. Найти лучший темп на длинных (15+ км)
        long_runs = session.query(Training).filter(
            Training.user_id == user_id,
            Training.type == 'actual',
            Training.distance_km >= 15,
            Training.duration_min.isnot(None),
            Training.duration_min > 0
        ).all()

        if long_runs:
            best_pace = None
            best_long_run = None
            for t in long_runs:
                pace_sec = (t.duration_min * 60) / t.distance_km
                if best_pace is None or pace_sec < best_pace:
                    best_pace = pace_sec
                    best_long_run = t

            if best_long_run:
                signal = "intermediate" if best_pace < 420 else "beginner"  # 7:00/км = 420 сек
                evidence.append({
                    "type": "long_run_pace",
                    "date": best_long_run.date.strftime("%d.%m.%Y") if best_long_run.date else None,
                    "distance_km": round(best_long_run.distance_km, 1),
                    "time": f"{best_long_run.duration_min} мин",
                    "pace": _format_pace(int(best_pace)),
                    "result": f"темп {_format_pace(int(best_pace))}/км",
                    "signal": signal,
                    "explanation": f"темп < 7:00/км на длинной → intermediate"
                })
        elif max_dist_training and max_dist_training.distance_km and max_dist_training.distance_km < 15:
            missing.append(f"Нет длинных тренировок 15+ км (макс. {max_dist_training.distance_km:.1f} км)")

        # 4. Статистика за 4 недели (объём, частота)
        four_weeks_ago = time_utils.today() - timedelta(days=28)
        recent_stats = session.query(
            func.count(Training.id).label('count'),
            func.sum(Training.distance_km).label('distance')
        ).filter(
            Training.user_id == user_id,
            Training.type == 'actual',
            Training.date >= four_weeks_ago
        ).first()

        if recent_stats and recent_stats.count and recent_stats.count >= 4:
            weekly_km = (recent_stats.distance or 0) / 4
            weekly_trainings = recent_stats.count / 4

            if weekly_km >= 40 and weekly_trainings >= 4:
                evidence.append({
                    "type": "weekly_volume",
                    "period": "последние 4 недели",
                    "distance_km": round(weekly_km, 1),
                    "trainings_per_week": round(weekly_trainings, 1),
                    "result": f"{weekly_km:.0f} км/нед, {weekly_trainings:.1f} тр/нед",
                    "signal": "intermediate",
                    "explanation": "≥40 км/нед + ≥4 тренировки → intermediate"
                })

    # Определяем достаточно ли данных
    has_key_evidence = any(e['type'] in ['vdot_10k', 'vdot_half', 'max_distance', 'long_run_pace']
                          and e.get('signal') in ['intermediate', 'advanced'] for e in evidence)

    return {
        "evidence": evidence,
        "missing": missing,
        "has_sufficient_data": len(evidence) > 0 and (has_key_evidence or len(missing) == 0)
    }


def format_level_explanation(level: str, stats: dict) -> str:
    """Форматирует объяснение определённого уровня для пользователя (старая версия)"""
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


def format_level_with_evidence(user_id: int, level: str, stats: dict) -> str:
    """
    Форматирует объяснение уровня С КОНКРЕТНЫМИ ТРЕНИРОВКАМИ.

    Показывает:
    - Список тренировок, повлиявших на определение
    - Что означает каждая тренировка
    - Итоговый уровень
    - Если данных не хватает — что нужно для точного определения

    Args:
        user_id: ID пользователя
        level: Определённый уровень (beginner/intermediate/advanced)
        stats: Статистика из detect_fitness_level()

    Returns:
        Текст для отображения пользователю
    """
    level_names = {
        "beginner": "🟢 Новичок",
        "intermediate": "🟡 Средний",
        "advanced": "🔴 Опытный"
    }
    level_name = level_names.get(level, level)

    # Получаем доказательства
    evidence_data = get_level_evidence(user_id)
    evidence_list = evidence_data.get("evidence", [])
    missing_list = evidence_data.get("missing", [])

    text = "📊 **Анализ твоего уровня**\n\n"

    if evidence_list:
        text += "**Ключевые тренировки:**\n"

        # Группируем по типу и показываем самые важные
        type_labels = {
            "max_distance": "📏 Макс. дистанция",
            "vdot_10k": "🏃 10 км",
            "vdot_half": "🏃 Полумарафон",
            "long_run_pace": "⏱ Темп на длинных",
            "weekly_volume": "📈 Недельный объём"
        }

        for e in evidence_list:
            e_type = e.get("type", "")
            label = type_labels.get(e_type, e_type)

            # Формируем строку
            parts = []
            if e.get("date"):
                parts.append(e["date"])
            if e.get("distance_km"):
                parts.append(f"{e['distance_km']} км")
            if e.get("time") and e_type in ["vdot_10k", "vdot_half"]:
                parts.append(f"за {e['time']}")
            result = e.get("result", "")

            text += f"• {label}: "
            if parts:
                text += f"{', '.join(parts)}"
            if result:
                text += f" → **{result}**\n"
            else:
                text += "\n"

    if missing_list:
        text += "\n**Чего не хватает для точного определения:**\n"
        for m in missing_list:
            text += f"• {m}\n"

    text += f"\n✅ **Твой уровень: {level_name}**"

    # Добавляем пояснение если уровень beginner из-за нехватки данных
    if level == "beginner" and missing_list and not evidence_data.get("has_sufficient_data"):
        text += "\n\n_Уровень будет уточнён автоматически после появления новых данных._"

    return text


def format_level_for_weekly_report(user_id: int) -> Optional[str]:
    """
    Форматирует секцию уровня для еженедельного отчёта.

    Returns:
        Текст секции или None если нет данных
    """
    level, stats = detect_fitness_level(user_id)

    if not level:
        return None

    evidence_data = get_level_evidence(user_id)
    evidence_list = evidence_data.get("evidence", [])

    if not evidence_list:
        return None

    level_names = {
        "beginner": "🟢 Новичок",
        "intermediate": "🟡 Средний",
        "advanced": "🔴 Опытный"
    }
    level_name = level_names.get(level, level)

    text = f"**Твой уровень: {level_name}**\n"
    text += "Основано на:\n"

    # Показываем только ключевые доказательства (не все)
    shown = 0
    for e in evidence_list:
        if shown >= 3:
            break
        if e.get("signal") in ["intermediate", "advanced"]:
            if e.get("type") == "vdot_10k":
                text += f"• 10 км за {e.get('time', 'N/A')} → {e.get('result', '')}\n"
            elif e.get("type") == "vdot_half":
                text += f"• Полумарафон за {e.get('time', 'N/A')} → {e.get('result', '')}\n"
            elif e.get("type") == "max_distance":
                text += f"• Макс. дистанция: {e.get('distance_km', '')} км\n"
            elif e.get("type") == "long_run_pace":
                text += f"• Длинная {e.get('distance_km', '')} км с темпом {e.get('pace', '')}/км\n"
            shown += 1

    return text
