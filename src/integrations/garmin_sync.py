"""Интеграция с Garmin Connect"""
from datetime import date, timedelta
from typing import List, Dict, Any
from garminconnect import Garmin, GarminConnectConnectionError, GarminConnectAuthenticationError

from ..utils.config import Config
from ..utils.logger import logger
from ..database.db import db, Training


class GarminSync:
    """Синхронизация с Garmin Connect"""

    def __init__(self):
        """Инициализация"""
        self.email = Config.GARMIN_EMAIL
        self.password = Config.GARMIN_PASSWORD
        self.client = None

    def login(self) -> bool:
        """
        Авторизация в Garmin Connect

        Returns:
            True если успешно, False если ошибка
        """
        try:
            logger.info("Авторизация в Garmin Connect...")
            self.client = Garmin(self.email, self.password)
            self.client.login()
            logger.info("✅ Авторизация успешна")
            return True
        except GarminConnectAuthenticationError as e:
            logger.error(f"❌ Ошибка авторизации Garmin: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Garmin: {e}")
            return False

    def get_activities_for_date(self, target_date: date) -> List[Dict[str, Any]]:
        """
        Получить активности за день с детальными данными

        Args:
            target_date: Дата

        Returns:
            Список активностей с зонами пульса
        """
        if not self.client:
            if not self.login():
                return []

        try:
            date_str = target_date.isoformat()
            activities = self.client.get_activities_by_date(date_str, date_str)

            if not activities or not isinstance(activities, list):
                return []

            # Фильтруем только беговые и силовые
            running_types = ['running', 'trail_running', 'treadmill_running']
            strength_types = ['strength_training', 'cardio_training']

            filtered = []
            for activity in activities:
                activity_type = activity.get('activityType', {}).get('typeKey', '').lower()
                if any(rt in activity_type for rt in running_types + strength_types):
                    # Получаем детальные данные (включая зоны пульса)
                    activity_id = activity.get('activityId')
                    if activity_id:
                        try:
                            # Получаем splits (содержат зоны)
                            splits = self.client.get_activity_splits(activity_id)
                            if splits:
                                activity['splits'] = splits
                        except Exception as e:
                            logger.debug(f"Не удалось получить splits для {activity_id}: {e}")

                    filtered.append(activity)

            logger.info(f"Найдено {len(filtered)} тренировок за {target_date}")
            return filtered

        except Exception as e:
            logger.error(f"Ошибка получения активностей за {target_date}: {e}")
            return []

    def parse_hr_zones(self, activity: Dict[str, Any]) -> Dict[str, int]:
        """
        Парсинг зон пульса из активности

        Args:
            activity: Данные активности от Garmin

        Returns:
            Словарь с временем в зонах (в секундах)
        """
        zones = {}

        # Формат 1: timeInHrZone0, timeInHrZone1, ...
        for i in range(5):
            zone_key = f'timeInHrZone{i}'
            if zone_key in activity and activity[zone_key] is not None:
                zone_seconds = activity[zone_key]
                if zone_seconds > 0:
                    zones[f'z{i+1}'] = zone_seconds

        # Формат 2: массив hrZones
        if not zones and 'hrZones' in activity:
            hr_zones_list = activity.get('hrZones', [])
            if isinstance(hr_zones_list, list):
                for zone_obj in hr_zones_list:
                    zone_num = zone_obj.get('zoneNumber') or zone_obj.get('zone')
                    time_val = zone_obj.get('timeInZone') or zone_obj.get('secsInZone')
                    if zone_num is not None and time_val and time_val > 0:
                        zones[f'z{zone_num}'] = time_val

        # Формат 3: averageHRTimeInZones
        if not zones and 'averageHRTimeInZones' in activity:
            avg_zones = activity.get('averageHRTimeInZones', {})
            for i in range(1, 6):
                zone_time = avg_zones.get(f'zone{i}')
                if zone_time and zone_time > 0:
                    zones[f'z{i}'] = zone_time

        return zones if zones else None

    def parse_activity(self, activity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Парсинг активности в формат для БД

        Args:
            activity: Данные активности от Garmin

        Returns:
            Словарь с данными для сохранения
        """
        distance_m = activity.get('distance', 0)
        duration_sec = activity.get('duration', 0)

        # Средний темп (сек/км)
        avg_pace = None
        if distance_m > 0 and duration_sec > 0:
            pace_sec_per_km = (duration_sec / (distance_m / 1000))
            pace_min = int(pace_sec_per_km // 60)
            pace_sec = int(pace_sec_per_km % 60)
            avg_pace = f"{pace_min}:{pace_sec:02d}"

        # Парсинг зон пульса
        hr_zones = self.parse_hr_zones(activity)

        return {
            'distance_km': distance_m / 1000 if distance_m else None,
            'duration_min': duration_sec // 60 if duration_sec else None,
            'avg_pace': avg_pace,
            'avg_hr': activity.get('averageHR'),
            'max_hr': activity.get('maxHR'),
            'elevation_m': int(activity.get('elevationGain', 0)),
            'hr_zones': hr_zones,
            'notes': activity.get('activityName', '')
        }

    def sync_today(self, user_id: int) -> int:
        """
        Синхронизация тренировок за сегодня

        Args:
            user_id: ID пользователя

        Returns:
            Количество сохранённых тренировок
        """
        today = date.today()
        return self.sync_date(user_id, today)

    def sync_date(self, user_id: int, target_date: date) -> int:
        """
        Синхронизация тренировок за конкретную дату

        Args:
            user_id: ID пользователя
            target_date: Дата для синхронизации

        Returns:
            Количество сохранённых тренировок
        """
        activities = self.get_activities_for_date(target_date)

        if not activities:
            logger.info(f"Нет тренировок за {target_date}")
            return 0

        saved_count = 0

        with db.get_session() as session:
            for activity in activities:
                parsed = self.parse_activity(activity)

                # Проверка, не сохранена ли уже
                existing = session.query(Training).filter_by(
                    user_id=user_id,
                    date=target_date,
                    distance_km=parsed['distance_km']
                ).first()

                if existing:
                    logger.debug(f"Тренировка {target_date} уже существует, пропуск")
                    continue

                training = Training(
                    user_id=user_id,
                    date=target_date,
                    type='actual',
                    **parsed
                )

                session.add(training)
                saved_count += 1
                logger.info(f"Сохранена тренировка: {target_date}, {parsed['distance_km']}км")

        return saved_count


# Глобальный экземпляр
garmin_sync = GarminSync()
