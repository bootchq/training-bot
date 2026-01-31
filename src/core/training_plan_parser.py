"""Парсер плана тренировок из markdown"""
import re
from datetime import date
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from ..utils.logger import logger


class TrainingPlanParser:
    """Парсер markdown файла с планом тренировок"""

    # Маппинг типов тренировок
    WORKOUT_TYPE_MAP = {
        'легк': 'easy',
        'easy': 'easy',
        'восстановительн': 'easy',
        'recovery': 'easy',
        'темп': 'tempo',
        'tempo': 'tempo',
        'threshold': 'tempo',
        'порог': 'tempo',
        'крейсов': 'tempo',
        'интервал': 'intervals',
        'intervals': 'intervals',
        'vo2max': 'intervals',
        'фартлек': 'fartlek',
        'fartlek': 'fartlek',
        'длинн': 'long',
        'long': 'long',
        'марафон': 'race',
        'dwt': 'race',
        'тарки': 'race',
        'race': 'race',
        'отдых': 'rest',
        'rest': 'rest',
        'активац': 'easy',
        'разминка': 'easy'
    }

    # Маппинг месяцев
    MONTHS_MAP = {
        '01': 1, '02': 2, '03': 3, '04': 4, '05': 5, '06': 6,
        '07': 7, '08': 8, '09': 9, '10': 10, '11': 11, '12': 12
    }

    def __init__(self, file_path: str):
        """
        Инициализация парсера

        Args:
            file_path: Путь к markdown файлу с планом
        """
        self.file_path = Path(file_path)
        self.trainings = []

    def parse(self) -> List[Dict[str, Any]]:
        """
        Парсинг файла с планом

        Returns:
            Список тренировок с данными
        """
        if not self.file_path.exists():
            logger.error(f"Файл не найден: {self.file_path}")
            return []

        try:
            with open(self.file_path, encoding='utf-8') as f:
                content = f.read()

            # Разделить на секции недель
            week_sections = re.split(r'###\s+Неделя \d+', content)

            for section in week_sections[1:]:  # Пропускаем преамбулу
                self._parse_week_section(section)

            logger.info(f"Распарсено {len(self.trainings)} тренировок")
            return self.trainings

        except Exception as e:
            logger.error(f"Ошибка парсинга плана: {e}")
            return []

    def _parse_week_section(self, section: str):
        """Парсинг секции недели"""
        # Найти все тренировки в секции
        # Паттерн: **День ДД.ММ — Название**
        training_pattern = r'\*\*([А-Яа-я]+)\s+(\d{2}\.\d{2})\s*—\s*([^\*]+)\*\*'
        matches = re.finditer(training_pattern, section)

        for match in matches:
            day_name = match.group(1)
            date_str = match.group(2)
            workout_name = match.group(3).strip()

            # Найти описание тренировки (всё до следующей тренировки или конца секции)
            start_pos = match.end()
            next_match = re.search(training_pattern, section[start_pos:])
            if next_match:
                end_pos = start_pos + next_match.start()
            else:
                end_pos = len(section)

            description = section[start_pos:end_pos].strip()

            # Распарсить детали
            training_data = self._parse_training_details(
                day_name, date_str, workout_name, description
            )

            if training_data:
                self.trainings.append(training_data)

    def _parse_training_details(
        self, day_name: str, date_str: str, workout_name: str, description: str
    ) -> Optional[Dict[str, Any]]:
        """Парсинг деталей тренировки"""
        try:
            # Парсинг даты
            training_date = self._parse_date(date_str)
            if not training_date:
                return None

            # Определение типа тренировки
            workout_type = self._detect_workout_type(workout_name)

            # Извлечение длительности
            duration = self._extract_duration(description)

            # Извлечение расстояния
            distance = self._extract_distance(description)

            # Извлечение зон
            zones = self._extract_zones(description)

            return {
                'date': training_date,
                'workout_type': workout_type,
                'workout_name': workout_name,
                'duration_min': duration,
                'distance_km': distance,
                'target_zone': zones,
                'description': description[:500]  # Ограничиваем длину
            }

        except Exception as e:
            logger.debug(f"Ошибка парсинга тренировки {date_str}: {e}")
            return None

    def _parse_date(self, date_str: str) -> Optional[date]:
        """
        Парсинг даты из формата ДД.ММ

        Args:
            date_str: Строка даты в формате "29.12"

        Returns:
            Объект date или None
        """
        try:
            day, month = date_str.split('.')
            day = int(day)
            month = int(month)

            # Определяем год: декабрь 2025, остальное 2026
            year = 2025 if month == 12 else 2026

            return date(year, month, day)

        except Exception as e:
            logger.debug(f"Ошибка парсинга даты {date_str}: {e}")
            return None

    def _detect_workout_type(self, workout_name: str) -> str:
        """Определение типа тренировки по названию"""
        workout_name_lower = workout_name.lower()

        for keyword, workout_type in self.WORKOUT_TYPE_MAP.items():
            if keyword in workout_name_lower:
                return workout_type

        return 'easy'  # По умолчанию

    def _extract_duration(self, description: str) -> Optional[int]:
        """Извлечение длительности в минутах"""
        # Паттерн: **~80 минут** или **~120 минут (20км)**
        pattern = r'\*\*~(\d+)\s+минут'
        match = re.search(pattern, description)

        if match:
            return int(match.group(1))

        return None

    def _extract_distance(self, description: str) -> Optional[float]:
        """Извлечение расстояния в км"""
        # Паттерн: (20км) или (18–20км)
        pattern = r'\((\d+)(?:–\d+)?км'
        match = re.search(pattern, description)

        if match:
            return float(match.group(1))

        return None

    def _extract_zones(self, description: str) -> Optional[str]:
        """Извлечение целевых зон пульса"""
        zones = set()

        # Поиск всех упоминаний зон
        zone_pattern = r'z([1-5])'
        matches = re.findall(zone_pattern, description.lower())

        for zone_num in matches:
            zones.add(f'z{zone_num}')

        if zones:
            return ', '.join(sorted(zones))

        return None


def parse_training_plan(file_path: str) -> List[Dict[str, Any]]:
    """
    Упрощённый интерфейс для парсинга плана

    Args:
        file_path: Путь к markdown файлу

    Returns:
        Список тренировок
    """
    parser = TrainingPlanParser(file_path)
    return parser.parse()
