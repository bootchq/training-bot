"""
Integration тесты для парсинга времени тренировок

Проверяет что бот правильно распознаёт разные форматы ввода времени:
- Простые числа: 60, 90, 120
- Диапазоны часов: "с 19 до 21", "19-21"
- Диапазоны с минутами: "с 19:10 до 20:40", "19:30-21:00"
"""
import re

import pytest


def parse_training_time(text: str) -> int:
    """
    Парсинг времени тренировки из текстового ввода

    Копия логики из telegram_bot.py для тестирования
    """
    time_min = None

    try:
        # Пробуем распарсить как простое число
        time_min = int(text)
    except ValueError:
        # Пробуем распарсить "с X до Y" или "с X:MM до Y:MM"
        # Паттерны: "с 19 до 21", "19-21", "с 19:10 до 20:40", "19:30-21:00"
        pattern = r'(?:с\s*)?(\d{1,2})(?::(\d{2}))?(?:\s*до\s*|\s*-\s*)(\d{1,2})(?::(\d{2}))?'
        match = re.search(pattern, text.lower())

        if match:
            start_hour = int(match.group(1))
            start_min = int(match.group(2)) if match.group(2) else 0
            end_hour = int(match.group(3))
            end_min = int(match.group(4)) if match.group(4) else 0

            # Переводим в минуты от начала дня
            start_total = start_hour * 60 + start_min
            end_total = end_hour * 60 + end_min

            # Вычисляем разницу
            if end_total > start_total:
                time_min = end_total - start_total
            else:
                # Через полночь (например, с 22:00 до 02:00)
                time_min = (24 * 60 - start_total) + end_total

    return time_min


class TestTimeParsingSimpleNumbers:
    """Тесты парсинга простых чисел"""

    def test_parse_60_minutes(self):
        """Ввод: 60 → 60 минут"""
        result = parse_training_time("60")
        assert result == 60

    def test_parse_90_minutes(self):
        """Ввод: 90 → 90 минут"""
        result = parse_training_time("90")
        assert result == 90

    def test_parse_120_minutes(self):
        """Ввод: 120 → 120 минут"""
        result = parse_training_time("120")
        assert result == 120

    def test_parse_45_minutes(self):
        """Ввод: 45 → 45 минут"""
        result = parse_training_time("45")
        assert result == 45


class TestTimeParsingHourRanges:
    """Тесты парсинга диапазонов часов"""

    def test_parse_19_to_21(self):
        """Ввод: 'с 19 до 21' → 120 минут"""
        result = parse_training_time("с 19 до 21")
        assert result == 120

    def test_parse_19_21_dash(self):
        """Ввод: '19-21' → 120 минут"""
        result = parse_training_time("19-21")
        assert result == 120

    def test_parse_7_to_9(self):
        """Ввод: 'с 7 до 9' → 120 минут"""
        result = parse_training_time("с 7 до 9")
        assert result == 120

    def test_parse_without_prefix(self):
        """Ввод: '18 до 20' → 120 минут"""
        result = parse_training_time("18 до 20")
        assert result == 120


class TestTimeParsingHourMinuteRanges:
    """Тесты парсинга диапазонов с минутами"""

    def test_parse_19_10_to_20_40(self):
        """Ввод: 'с 19:10 до 20:40' → 90 минут (ОСНОВНОЙ ТЕСТ)"""
        result = parse_training_time("с 19:10 до 20:40")
        assert result == 90, f"Ожидалось 90, получено {result}"

    def test_parse_19_30_to_21_00(self):
        """Ввод: '19:30-21:00' → 90 минут"""
        result = parse_training_time("19:30-21:00")
        assert result == 90

    def test_parse_18_15_to_19_45(self):
        """Ввод: 'с 18:15 до 19:45' → 90 минут"""
        result = parse_training_time("с 18:15 до 19:45")
        assert result == 90

    def test_parse_7_00_to_8_30(self):
        """Ввод: '7:00-8:30' → 90 минут"""
        result = parse_training_time("7:00-8:30")
        assert result == 90

    def test_parse_uppercase(self):
        """Ввод: 'С 19:10 ДО 20:40' → 90 минут (uppercase)"""
        result = parse_training_time("С 19:10 ДО 20:40")
        assert result == 90


class TestTimeParsingEdgeCases:
    """Тесты граничных случаев"""

    def test_parse_through_midnight(self):
        """Ввод: 'с 22:00 до 02:00' → 240 минут (через полночь)"""
        result = parse_training_time("с 22:00 до 02:00")
        assert result == 240

    def test_parse_short_time(self):
        """Ввод: 'с 19:00 до 19:30' → 30 минут"""
        result = parse_training_time("с 19:00 до 19:30")
        assert result == 30

    def test_parse_invalid_format(self):
        """Ввод: 'какой-то текст' → None"""
        result = parse_training_time("какой-то текст")
        assert result is None

    def test_parse_mixed_format(self):
        """Ввод: 'с 19 до 20:30' → 90 минут (смешанный формат)"""
        result = parse_training_time("с 19 до 20:30")
        assert result == 90


if __name__ == "__main__":
    # Запуск тестов напрямую
    pytest.main([__file__, "-v"])
