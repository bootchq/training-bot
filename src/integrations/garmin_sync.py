"""Интеграция с Garmin Connect"""
import shutil
from datetime import date
from datetime import timedelta
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from garminconnect import Garmin
from garminconnect import GarminConnectAuthenticationError

from ..database.db import Training
from ..database.db import db
from ..utils.config import Config
from ..utils.logger import logger


class GarminSync:
    """Синхронизация с Garmin Connect"""

    def __init__(self):
        """Инициализация"""
        self.email = Config.GARMIN_EMAIL
        self.password = Config.GARMIN_PASSWORD
        self.client = None
        self.current_user_id = None

    def clear_session(self) -> bool:
        """
        Очистить кешированную сессию Garmin (OAuth tokens)

        Библиотека garminconnect использует garth, который сохраняет
        OAuth tokens в ~/.garth/. При сбросе пользователя нужно удалить
        эти файлы, иначе авторизация пройдёт с неправильными credentials.

        Returns:
            True если успешно или директории нет
        """
        try:
            garth_dir = Path.home() / '.garth'
            if garth_dir.exists():
                shutil.rmtree(garth_dir)
                logger.info(f"✅ Удалена директория с OAuth tokens: {garth_dir}")
            else:
                logger.debug(f"Директория {garth_dir} не существует, пропуск")

            # Сбрасываем текущий client
            self.client = None
            self.current_user_id = None

            return True
        except Exception as e:
            logger.error(f"❌ Ошибка при очистке сессии Garmin: {e}")
            return False

    def login(self, email: str = None, password: str = None) -> bool:
        """
        Авторизация в Garmin Connect

        Args:
            email: Email от Garmin (если None - используется из Config)
            password: Пароль от Garmin (если None - используется из Config)

        Returns:
            True если успешно, False если ошибка
        """
        email = email or self.email
        password = password or self.password

        if not email or not password:
            logger.error("❌ Не указаны учетные данные Garmin")
            return False

        try:
            logger.info(f"Авторизация в Garmin Connect ({email})...")
            self.client = Garmin(email, password)
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

            # Получаем последние 100 активностей (покрывает ~3 месяца при тренировках каждый день)
            all_activities = self.client.get_activities(0, 100)

            if not all_activities or not isinstance(all_activities, list):
                return []

            # Фильтруем по дате (startTimeLocal формат: "2026-01-30T07:00:00.0")
            activities = [
                act for act in all_activities
                if act.get('startTimeLocal', '').startswith(date_str)
            ]

            # Фильтруем только беговые и кардио
            running_types = ['running', 'trail_running', 'treadmill_running']
            cardio_types = ['cardio_training']
            allowed_types = running_types + cardio_types

            filtered = []
            for activity in activities:
                activity_type = activity.get('activityType', {}).get('typeKey', '').lower()
                if activity_type in allowed_types:
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

    def get_lactate_threshold(self) -> Optional[int]:
        """
        Получить LTHR (Lactate Threshold Heart Rate) из Garmin

        Пробует несколько источников:
        1. get_lactate_threshold() — прямой запрос
        2. get_max_metrics() — альтернативный endpoint

        Returns:
            LTHR в уд/мин или None
        """
        if not self.client:
            if not self.login():
                return None

        try:
            # Источник 1: Прямой запрос LTHR
            lt_data = self.client.get_lactate_threshold(latest=True)
            logger.info(f"Ответ get_lactate_threshold: {lt_data}")

            # Обработка разных форматов ответа (может быть list или dict)
            if isinstance(lt_data, list) and lt_data:
                lt_data = lt_data[0]

            if lt_data and isinstance(lt_data, dict):
                # Проверяем разные возможные ключи
                lthr = (lt_data.get('lactateThresholdHeartRate') or
                        lt_data.get('lactateThresholdHR') or
                        lt_data.get('thresholdHeartRate') or
                        lt_data.get('lthr'))
                if lthr:
                    logger.info(f"LTHR из Garmin: {lthr} уд/мин")
                    return int(lthr)

            # Источник 2: max_metrics (альтернатива)
            logger.info("LTHR не найден в get_lactate_threshold, пробую get_max_metrics...")
            try:
                max_metrics = self.client.get_max_metrics(date.today().isoformat())
                logger.info(f"Ответ get_max_metrics: {max_metrics}")

                if max_metrics and isinstance(max_metrics, dict):
                    # Проверяем есть ли threshold данные
                    threshold = max_metrics.get('lactateThresholdHeartRate')
                    if threshold:
                        logger.info(f"LTHR из max_metrics: {threshold} уд/мин")
                        return int(threshold)
            except Exception as e:
                logger.info(f"get_max_metrics не доступен: {e}")

            logger.info("LTHR не найден в данных Garmin")
            return None

        except Exception as e:
            logger.warning(f"Не удалось получить LTHR: {e}")
            return None

    def get_personal_records(self) -> Dict[str, Dict[str, Any]]:
        """
        Получить персональные рекорды из Garmin

        Returns:
            Словарь рекордов: {"5k": {"time_seconds": 1500, "date": "2024-01-15"}, ...}
        """
        if not self.client:
            if not self.login():
                return {}

        try:
            # Получаем персональные рекорды
            pr_data = self.client.get_personal_record()

            records = {}
            if pr_data and isinstance(pr_data, list):
                # Маппинг типов рекордов Garmin на наши
                distance_mapping = {
                    'PR_5K': '5k',
                    'PR_10K': '10k',
                    'PR_HALF_MARATHON': 'half',
                    'PR_MARATHON': 'marathon',
                    'FASTEST_5K': '5k',
                    'FASTEST_10K': '10k',
                    'FASTEST_HALF_MARATHON': 'half',
                    'FASTEST_MARATHON': 'marathon',
                }

                for record in pr_data:
                    record_type = record.get('prTypePk') or record.get('typeKey', '')

                    # Проверяем оба варианта маппинга
                    our_type = distance_mapping.get(record_type)
                    if not our_type:
                        # Пробуем найти по частичному совпадению
                        for garmin_key, our_key in distance_mapping.items():
                            if garmin_key in record_type.upper():
                                our_type = our_key
                                break

                    if our_type:
                        time_seconds = record.get('elapsedTime') or record.get('value')
                        if time_seconds:
                            # Преобразуем если нужно (иногда приходит в мс)
                            if time_seconds > 86400:  # больше суток = миллисекунды
                                time_seconds = time_seconds / 1000

                            record_date = record.get('prDate') or record.get('activityStartDateLocal')

                            # Сохраняем лучший результат (меньшее время)
                            if our_type not in records or time_seconds < records[our_type]['time_seconds']:
                                records[our_type] = {
                                    'time_seconds': int(time_seconds),
                                    'date': record_date
                                }
                                logger.info(f"PR {our_type}: {self._format_time(int(time_seconds))}")

            logger.info(f"Получено {len(records)} персональных рекордов из Garmin")
            return records

        except Exception as e:
            logger.warning(f"Не удалось получить персональные рекорды: {e}")
            return {}

    def _format_time(self, seconds: int) -> str:
        """Форматирование времени в mm:ss или hh:mm:ss"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    def sync_last_60_days(self, user_id: int) -> Tuple[int, Optional[int], Dict[str, Dict]]:
        """
        Синхронизация тренировок за последние 60 дней + LTHR + Personal Records

        Args:
            user_id: ID пользователя

        Returns:
            Tuple (количество тренировок, LTHR, personal_records)
        """
        logger.info(f"Начинаю синхронизацию 60 дней для user_id={user_id}")

        # Получаем LTHR из Garmin (тест лактатного порога)
        lthr = self.get_lactate_threshold()
        lthr_source = "garmin" if lthr else None

        # Получаем персональные рекорды
        personal_records = self.get_personal_records()

        # Синхронизируем тренировки за 60 дней
        total_saved = 0
        today = date.today()

        for days_ago in range(60):
            target_date = today - timedelta(days=days_ago)
            saved = self.sync_date(user_id, target_date)
            total_saved += saved

        # Если LTHR не получен из Garmin — рассчитываем по max HR из тренировок
        if not lthr:
            lthr = self._estimate_lthr_from_trainings(user_id)
            lthr_source = "estimated" if lthr else None

        logger.info(
            f"Синхронизация завершена: {total_saved} тренировок, "
            f"LTHR={lthr} (источник: {lthr_source}), PR={len(personal_records)}"
        )
        return total_saved, lthr, personal_records

    def _estimate_lthr_from_trainings(self, user_id: int) -> Optional[int]:
        """
        Оценка LTHR по max HR из тренировок (fallback если Garmin не отдаёт LTHR)

        Формула: LTHR ≈ 85% от max HR (Joe Friel)

        Args:
            user_id: ID пользователя

        Returns:
            Оценочный LTHR или None
        """
        from ..database.db import db

        trainings = db.get_user_trainings(user_id, limit=60)
        if not trainings:
            return None

        # Находим максимальный пульс из всех тренировок
        max_hrs = [t.max_hr for t in trainings if t.max_hr and t.max_hr > 100]
        if not max_hrs:
            return None

        max_hr = max(max_hrs)

        # LTHR ≈ 85% от max HR (консервативная оценка по Joe Friel)
        lthr = int(max_hr * 0.85)

        logger.info(f"LTHR рассчитан по max HR: {lthr} уд/мин (max HR={max_hr})")
        return lthr

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

    def sync_date_for_user(self, user_id: int, target_date: date) -> int:
        """
        Синхронизация тренировок для конкретного пользователя

        Args:
            user_id: ID пользователя (внутренний)
            target_date: Дата для синхронизации

        Returns:
            Количество сохранённых тренировок
        """
        # Получаем учетные данные пользователя
        credentials = db.get_user_garmin_credentials(user_id)

        if not credentials:
            logger.warning(f"Нет учетных данных Garmin для пользователя {user_id}")
            return 0

        email, password = credentials

        # Авторизуемся с учетными данными пользователя
        if not self.login(email, password):
            logger.error(f"Не удалось авторизоваться в Garmin для пользователя {user_id}")
            return 0

        # Синхронизируем
        return self.sync_date(user_id, target_date)


# Глобальный экземпляр
garmin_sync = GarminSync()
