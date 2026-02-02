"""Утилиты для работы со временем в правильной таймзоне"""
from datetime import date
from datetime import datetime
from datetime import time as dt_time
from typing import List, Optional
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


def parse_date_flexible(text: str) -> Optional[date]:
    """
    Умный парсер дат — понимает разные форматы.

    Поддерживаемые форматы:
    - "15.03.2026", "15/03/2026", "15-03-2026"
    - "15 марта 2026", "15 мар 2026", "15 марта"
    - "март 15", "мар 15 2026"
    - "2026-03-15" (ISO)
    - "15.03", "15/03" (текущий год)

    Args:
        text: Строка с датой

    Returns:
        date объект или None если не удалось распарсить
    """
    import re

    text = text.strip().lower()
    current_year = today().year

    # Русские месяцы
    months_ru = {
        'январ': 1, 'янв': 1,
        'феврал': 2, 'фев': 2,
        'март': 3, 'мар': 3,
        'апрел': 4, 'апр': 4,
        'ма': 5, 'май': 5,
        'июн': 6,
        'июл': 7,
        'август': 8, 'авг': 8,
        'сентябр': 9, 'сен': 9,
        'октябр': 10, 'окт': 10,
        'ноябр': 11, 'ноя': 11,
        'декабр': 12, 'дек': 12
    }

    def find_month(s: str) -> Optional[int]:
        """Найти месяц в строке"""
        for name, num in months_ru.items():
            if name in s:
                return num
        return None

    def extract_numbers(s: str) -> List[int]:
        """Извлечь все числа из строки"""
        return [int(x) for x in re.findall(r'\d+', s)]

    try:
        # 1. ISO формат: 2026-03-15
        if re.match(r'^\d{4}-\d{2}-\d{2}$', text):
            return datetime.strptime(text, "%Y-%m-%d").date()

        # 2. Формат с разделителями: 15.03.2026, 15/03/2026, 15-03-2026
        match = re.match(r'^(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})$', text)
        if match:
            day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return date(year, month, day)

        # 3. Короткий формат: 15.03, 15/03 (текущий год)
        match = re.match(r'^(\d{1,2})[./\-](\d{1,2})$', text)
        if match:
            day, month = int(match.group(1)), int(match.group(2))
            return date(current_year, month, day)

        # 4. Текстовый формат с месяцем: "15 марта 2026", "15 марта", "15 мар 2026"
        month_num = find_month(text)
        if month_num:
            numbers = extract_numbers(text)
            if len(numbers) >= 1:
                day = numbers[0]
                # Проверяем, есть ли год (4-значное число)
                year = current_year
                for n in numbers:
                    if n >= 2020 and n <= 2100:
                        year = n
                        break
                # Если первое число > 31, возможно это год
                if day > 31 and len(numbers) >= 2:
                    day = numbers[1]
                return date(year, month_num, day)

        # 5. "март 15", "март 15 2026"
        match = re.search(r'(\d{1,2})', text)
        if match and month_num:
            day = int(match.group(1))
            numbers = extract_numbers(text)
            year = current_year
            for n in numbers:
                if n >= 2020 and n <= 2100:
                    year = n
                    break
            return date(year, month_num, day)

        return None

    except (ValueError, TypeError):
        return None
