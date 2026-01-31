"""Утилиты для работы со временем в правильной таймзоне"""
from datetime import datetime, date, time as dt_time
from zoneinfo import ZoneInfo


# Таймзона Москвы
MSK = ZoneInfo("Europe/Moscow")


def now() -> datetime:
    """
    Текущее время в таймзоне MSK (с учетом часового пояса)

    Returns:
        datetime с timezone MSK
    """
    return datetime.now(MSK)


def today() -> date:
    """
    Сегодняшняя дата в таймзоне MSK

    Returns:
        date объект для сегодняшнего дня в MSK
    """
    return now().date()


def to_msk(dt: datetime) -> datetime:
    """
    Конвертировать datetime в MSK таймзону

    Args:
        dt: datetime объект (с timezone или без)

    Returns:
        datetime в MSK таймзоне
    """
    if dt.tzinfo is None:
        # Если timezone не указан - считаем что это UTC
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(MSK)


def combine_datetime(d: date, t: dt_time) -> datetime:
    """
    Объединить date и time в datetime с MSK таймзоной

    Args:
        d: date объект
        t: time объект

    Returns:
        datetime в MSK таймзоне
    """
    return datetime.combine(d, t, tzinfo=MSK)
