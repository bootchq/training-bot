"""
Мониторинг тренировочной нагрузки по спортивной науке.

Реализует два золотых стандарта:

1. TRIMP (Training Impulse, Banister et al. 1991)
   Мера нагрузки одной тренировки учитывающая продолжительность и интенсивность.
   Формула: TRIMP = duration_min × hr_ratio × e^(1.92 × hr_ratio)
   где hr_ratio = (avg_hr - resting_hr) / (max_hr - resting_hr)

2. ACWR (Acute:Chronic Workload Ratio, Blanch & Gabbett 2016)
   Соотношение острой (7 дней) и хронической (28 дней) нагрузки.
   Безопасная зона: 0.8 – 1.3
   Зона риска: > 1.5 (риск травмы)
"""
from dataclasses import dataclass
from datetime import date
from datetime import timedelta
from math import exp
from typing import Dict
from typing import List
from typing import Optional

from ..database.db import Training
from ..database.db import db
from ..utils.logger import logger

# Пороги ACWR
ACWR_SWEET_SPOT_LOW = 0.8
ACWR_SWEET_SPOT_HIGH = 1.3
ACWR_CAUTION = 1.5

# Пороги Training Monotony (Foster et al.)
MONOTONY_HIGH = 2.0  # > 2.0 → слишком однообразно, риск перетренированности

# Дефолтные физиологические константы
DEFAULT_RESTING_HR = 50
DEFAULT_MAX_HR = 185


@dataclass
class WorkloadStatus:
    """Статус нагрузки пользователя"""
    # Абсолютные нагрузки
    acute_load: float       # Нагрузка за 7 дней (AU)
    chronic_load: float     # Нагрузка за 28 дней (AU)
    acwr: float             # Acute:Chronic Workload Ratio
    today_trimp: float      # TRIMP сегодняшней тренировки (0 если нет)

    # Недельные объёмы
    weekly_km: float        # км за текущую неделю
    prev_week_km: float     # км за прошлую неделю

    # Оценки
    risk_level: str         # "safe" / "caution" / "danger"
    risk_message: str       # Текстовое объяснение
    recommendation: str     # Рекомендация на следующую тренировку

    # Training Monotony
    monotony: float         # Индекс монотонности (1-7 дней)
    strain: float           # Training Strain = acute_load × monotony


def calculate_trimp(
    duration_min: int,
    avg_hr: Optional[int],
    max_hr: Optional[int] = None,
    resting_hr: int = DEFAULT_RESTING_HR
) -> float:
    """
    Рассчитать TRIMP для одной тренировки.

    Если avg_hr недоступен — используем упрощённую формулу:
    TRIMP = duration_min × intensity_factor
    где intensity_factor определяется по типу (0.5 для лёгкой, 1.0 норма, 1.5 интенсив)

    Args:
        duration_min: Продолжительность в минутах
        avg_hr: Средний пульс (опционально)
        max_hr: Максимальный пульс (опционально)
        resting_hr: Пульс покоя

    Returns:
        TRIMP в arbitrary units (AU)
    """
    if not duration_min or duration_min <= 0:
        return 0.0

    if avg_hr and avg_hr > 0:
        effective_max_hr = max_hr if max_hr and max_hr > avg_hr else DEFAULT_MAX_HR

        # Защита от деления на ноль
        hr_range = effective_max_hr - resting_hr
        if hr_range <= 0:
            hr_range = 100

        hr_ratio = (avg_hr - resting_hr) / hr_range
        hr_ratio = max(0.0, min(1.0, hr_ratio))  # clamp 0-1

        # Banister TRIMP formula
        trimp = duration_min * hr_ratio * exp(1.92 * hr_ratio)
    else:
        # Fallback: TRIMP = duration × 0.8 (средняя интенсивность)
        trimp = duration_min * 0.8

    return round(trimp, 1)


def get_user_trimp_series(user_id: int, days: int = 42) -> Dict[date, float]:
    """
    Получить ежедневный TRIMP за последние N дней.

    Args:
        user_id: ID пользователя
        days: Количество дней назад

    Returns:
        Словарь {дата: TRIMP}
    """
    today = date.today()
    cutoff = today - timedelta(days=days)

    trainings = db.get_user_trainings(user_id, limit=days * 3)
    if not trainings:
        return {}

    # Находим max HR пользователя для расчёта hr_ratio
    max_hrs = [t.max_hr for t in trainings if t.max_hr and t.max_hr > 100]
    user_max_hr = max(max_hrs) if max_hrs else DEFAULT_MAX_HR

    # Получаем resting HR из wellness surveys (последние 14 дней)
    user_resting_hr = _get_resting_hr(user_id)

    daily_trimp: Dict[date, float] = {}

    for training in trainings:
        if training.date < cutoff:
            continue
        if training.type not in ('actual',):
            continue

        trimp = calculate_trimp(
            duration_min=training.duration_min,
            avg_hr=training.avg_hr,
            max_hr=user_max_hr,
            resting_hr=user_resting_hr
        )

        # Суммируем если несколько тренировок за день
        if training.date in daily_trimp:
            daily_trimp[training.date] += trimp
        else:
            daily_trimp[training.date] = trimp

    return daily_trimp


def _get_resting_hr(user_id: int) -> int:
    """Получить средний пульс покоя из wellness surveys за последние 14 дней"""
    try:
        today = date.today()
        cutoff = today - timedelta(days=14)
        surveys = db.get_wellness_for_period(user_id, cutoff, today)
        rhr_values = [s.rhr for s in surveys if s.rhr and s.rhr > 30]
        if rhr_values:
            return int(sum(rhr_values) / len(rhr_values))
    except Exception:
        pass
    return DEFAULT_RESTING_HR


def calculate_acwr(daily_trimp: Dict[date, float]) -> tuple:
    """
    Рассчитать ACWR из серии ежедневных TRIMP.

    Acute load = средняя нагрузка за 7 дней × 7
    Chronic load = средняя нагрузка за 28 дней × 28

    Returns:
        (acute_load, chronic_load, acwr)
    """
    today = date.today()

    # Acute: сумма за последние 7 дней
    acute_sum = 0.0
    for i in range(7):
        d = today - timedelta(days=i)
        acute_sum += daily_trimp.get(d, 0.0)

    # Chronic: сумма за последние 28 дней
    chronic_sum = 0.0
    for i in range(28):
        d = today - timedelta(days=i)
        chronic_sum += daily_trimp.get(d, 0.0)

    # Средние нагрузки
    acute_avg = acute_sum / 7
    chronic_avg = chronic_sum / 28

    # ACWR
    if chronic_avg > 0:
        acwr = round(acute_avg / chronic_avg, 2)
    else:
        acwr = 1.0

    return round(acute_sum, 1), round(chronic_sum, 1), acwr


def calculate_training_monotony(daily_trimp: Dict[date, float]) -> tuple:
    """
    Training Monotony (Foster et al. 2001).

    Монотонность = mean(7 дней TRIMP) / std(7 дней TRIMP)
    Training Strain = Acute Load × Monotony

    Высокая монотонность (>2.0) коррелирует с перетренированностью
    даже при нормальном объёме.

    Returns:
        (monotony, strain)
    """
    today = date.today()
    week_values = []
    for i in range(7):
        d = today - timedelta(days=i)
        week_values.append(daily_trimp.get(d, 0.0))

    if not any(week_values):
        return 1.0, 0.0

    mean_load = sum(week_values) / 7

    # Стандартное отклонение
    variance = sum((v - mean_load) ** 2 for v in week_values) / 7
    std_load = variance ** 0.5

    monotony = mean_load / std_load if std_load > 0 else 1.0
    strain = sum(week_values) * monotony

    return round(monotony, 2), round(strain, 1)


def _assess_risk(acwr: float, monotony: float) -> tuple:
    """
    Оценить риск травмы и дать рекомендацию.

    Returns:
        (risk_level, risk_message, recommendation)
    """
    if acwr > ACWR_CAUTION:
        return (
            "danger",
            f"ACWR {acwr:.2f} — резкий скачок нагрузки. Высокий риск травмы.",
            "Снизь нагрузку на 30-40%. Лёгкий бег или полный отдых."
        )
    elif acwr > ACWR_SWEET_SPOT_HIGH:
        return (
            "caution",
            f"ACWR {acwr:.2f} — нагрузка выше нормы. Мониторь самочувствие.",
            "Можно продолжать, но не увеличивай объём. Приоритет сну."
        )
    elif acwr < ACWR_SWEET_SPOT_LOW:
        if acwr < 0.5:
            return (
                "caution",
                f"ACWR {acwr:.2f} — детренировка. Нагрузка слишком низкая.",
                "Постепенно увеличивай объём на 10% в неделю."
            )
        return (
            "safe",
            f"ACWR {acwr:.2f} — нагрузка ниже оптимума. Есть резерв.",
            "Можно добавить объём или интенсивность."
        )
    else:
        msg = f"ACWR {acwr:.2f} — оптимальная зона (0.8–1.3)."
        if monotony > MONOTONY_HIGH:
            return (
                "caution",
                msg + f" Но монотонность {monotony:.1f} — слишком однообразно.",
                "Добавь вариативность: чередуй лёгкие и тяжёлые дни."
            )
        return (
            "safe",
            msg + " Тренируйся уверенно.",
            "Продолжай по плану. Система в балансе."
        )


def get_workload_status(user_id: int) -> WorkloadStatus:
    """
    Получить полный статус нагрузки пользователя.

    Args:
        user_id: ID пользователя

    Returns:
        WorkloadStatus с ACWR, TRIMP, рисками и рекомендациями
    """
    daily_trimp = get_user_trimp_series(user_id, days=42)

    acute_load, chronic_load, acwr = calculate_acwr(daily_trimp)
    monotony, strain = calculate_training_monotony(daily_trimp)

    # TRIMP сегодня
    today_trimp = daily_trimp.get(date.today(), 0.0)

    # Недельные километры
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    prev_week_start = week_start - timedelta(days=7)

    trainings = db.get_user_trainings(user_id, limit=100)
    weekly_km = sum(
        t.distance_km for t in trainings
        if t.distance_km and t.type == 'actual'
        and t.date >= week_start and t.date <= today
    )
    prev_week_km = sum(
        t.distance_km for t in trainings
        if t.distance_km and t.type == 'actual'
        and t.date >= prev_week_start and t.date < week_start
    )

    risk_level, risk_message, recommendation = _assess_risk(acwr, monotony)

    return WorkloadStatus(
        acute_load=acute_load,
        chronic_load=chronic_load,
        acwr=acwr,
        today_trimp=today_trimp,
        weekly_km=round(weekly_km, 1),
        prev_week_km=round(prev_week_km, 1),
        risk_level=risk_level,
        risk_message=risk_message,
        recommendation=recommendation,
        monotony=monotony,
        strain=strain
    )


def format_workload_message(status: WorkloadStatus) -> str:
    """Форматирование статуса нагрузки для Telegram"""

    risk_icons = {
        "safe": "🟢",
        "caution": "🟡",
        "danger": "🔴"
    }
    icon = risk_icons.get(status.risk_level, "⚪")

    # Тренд объёма
    if status.prev_week_km > 0:
        km_change = status.weekly_km - status.prev_week_km
        km_trend = f"+{km_change:.1f}" if km_change >= 0 else f"{km_change:.1f}"
        km_trend_str = f" ({km_trend} км к прошлой)"
    else:
        km_trend_str = ""

    lines = [
        "**Нагрузка (ACWR / TRIMP)**",
        "",
        f"{icon} {status.risk_message}",
        "",
        "**Метрики:**",
        f"• ACWR: {status.acwr:.2f}  (зона 0.8–1.3)",
        f"• Острая нагрузка (7 дней): {status.acute_load:.0f} AU",
        f"• Хроническая (28 дней): {status.chronic_load:.0f} AU",
        f"• Монотонность: {status.monotony:.1f}  (норма < 2.0)",
        f"• Training Strain: {status.strain:.0f}",
        "",
        f"**Объём недели:** {status.weekly_km:.1f} км{km_trend_str}",
    ]

    if status.today_trimp > 0:
        lines.append(f"**Нагрузка сегодня:** {status.today_trimp:.0f} AU")

    lines.extend([
        "",
        f"**Рекомендация:** {status.recommendation}"
    ])

    return "\n".join(lines)
