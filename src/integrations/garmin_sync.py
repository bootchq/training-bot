"""Интеграция с Garmin Connect"""
import hashlib
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
        self.email = Config.GARMIN_EMAIL
        self.password = Config.GARMIN_PASSWORD
        self.client = None
        self.current_user_id = None

    def _get_token_path(self, email: str) -> Path:
        """
        Путь к сохранённым OAuth токенам для конкретного email.

        Используется для персистентного хранения garth токенов между
        перезапусками Railway контейнера. Требует Railway Volume на /data.
        """
        email_hash = hashlib.md5(email.lower().encode()).hexdigest()[:12]
        token_dir = Path(Config.GARTH_HOME) / email_hash
        token_dir.mkdir(parents=True, exist_ok=True)
        return token_dir

    def _tokens_exist(self, token_path: Path) -> bool:
        """Проверить наличие сохранённых токенов"""
        return (token_path / "oauth1_token.json").exists() or \
               (token_path / "oauth2_token.json").exists()

    def clear_session(self) -> bool:
        """
        Очистить кешированную сессию Garmin (OAuth tokens).

        Удаляет токены как из ~/.garth/ так и из /data/garth_tokens/,
        чтобы следующий login делал свежую авторизацию.
        """
        try:
            # Удаляем ~/.garth/ (дефолтная директория garth)
            garth_dir = Path.home() / '.garth'
            if garth_dir.exists():
                shutil.rmtree(garth_dir)
                logger.info(f"Удалена директория с OAuth tokens: {garth_dir}")

            # Удаляем сохранённые токены для текущего email
            if self.email:
                token_path = self._get_token_path(self.email)
                if token_path.exists():
                    shutil.rmtree(token_path)
                    logger.info(f"Удалены персистентные токены: {token_path}")

            self.client = None
            self.current_user_id = None
            return True
        except Exception as e:
            logger.error(f"Ошибка при очистке сессии Garmin: {e}")
            return False

    def login(self, email: str = None, password: str = None) -> bool:
        """
        Авторизация в Garmin Connect с поддержкой token persistence.

        Алгоритм:
        1. Если есть сохранённые токены → garth.load() (быстро, без SSO)
        2. Если нет или протухли → свежий login → сохранить токены

        Args:
            email: Email от Garmin (если None — из Config)
            password: Пароль от Garmin (если None — из Config)

        Returns:
            True если авторизация прошла
        """
        email = email or self.email
        password = password or self.password

        if not email or not password:
            logger.error("Не указаны учетные данные Garmin")
            return False

        token_path = self._get_token_path(email)

        # Пробуем загрузить сохранённые токены
        if self._tokens_exist(token_path):
            try:
                self.client = Garmin()
                self.client.login(tokenstore=str(token_path))
                logger.info(f"Garmin: загружены токены из {token_path}")
                return True
            except Exception as e:
                logger.warning(f"Garmin: токены устарели ({e}), повторная авторизация...")
                # Удаляем протухшие токены
                shutil.rmtree(token_path, ignore_errors=True)
                token_path.mkdir(parents=True, exist_ok=True)

        # Свежая авторизация через SSO
        try:
            logger.info(f"Garmin: авторизация через SSO ({email})...")
            self.client = Garmin(email, password)
            self.client.login()

            # Сохраняем токены для последующих запусков
            try:
                self.client.garth.dump(str(token_path))
                logger.info(f"Garmin: токены сохранены в {token_path}")
            except Exception as e:
                logger.warning(f"Garmin: не удалось сохранить токены: {e}")

            logger.info("Garmin: авторизация успешна")
            return True

        except GarminConnectAuthenticationError as e:
            logger.error(f"Ошибка авторизации Garmin (неверный логин/пароль): {e}")
            return False
        except Exception as e:
            logger.error(f"Ошибка подключения к Garmin: {e}")
            return False

    def get_activities_for_date(self, target_date: date) -> List[Dict[str, Any]]:
        """
        Получить активности за день с детальными данными.

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

            # Последние 100 активностей (~3 месяца при ежедневных тренировках)
            all_activities = self.client.get_activities(0, 100)

            if not all_activities or not isinstance(all_activities, list):
                return []

            # Фильтруем по дате (startTimeLocal: "2026-01-30T07:00:00.0")
            activities = [
                act for act in all_activities
                if act.get('startTimeLocal', '').startswith(date_str)
            ]

            # Только беговые и кардио
            allowed_types = [
                'running', 'trail_running', 'treadmill_running', 'cardio_training'
            ]

            filtered = []
            for activity in activities:
                activity_type = activity.get('activityType', {}).get('typeKey', '').lower()
                if activity_type in allowed_types:
                    activity_id = activity.get('activityId')
                    if activity_id:
                        try:
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
            # При ошибке авторизации — сбрасываем client для повторного login
            if "401" in str(e) or "auth" in str(e).lower():
                self.client = None
            return []

    def parse_hr_zones(self, activity: Dict[str, Any]) -> Dict[str, int]:
        """
        Парсинг зон пульса из активности.

        Returns:
            Словарь с временем в зонах (в секундах) или None
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
        Парсинг активности в формат для БД.

        Returns:
            Словарь с данными для сохранения
        """
        distance_m = activity.get('distance', 0)
        duration_sec = activity.get('duration', 0)

        avg_pace = None
        if distance_m > 0 and duration_sec > 0:
            pace_sec_per_km = duration_sec / (distance_m / 1000)
            pace_min = int(pace_sec_per_km // 60)
            pace_sec = int(pace_sec_per_km % 60)
            avg_pace = f"{pace_min}:{pace_sec:02d}"

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
        Получить LTHR (Lactate Threshold Heart Rate) из Garmin.

        Returns:
            LTHR в уд/мин или None
        """
        if not self.client:
            if not self.login():
                return None

        try:
            lt_data = self.client.get_lactate_threshold(latest=True)
            logger.info(f"Ответ get_lactate_threshold: {lt_data}")

            if isinstance(lt_data, list) and lt_data:
                lt_data = lt_data[0]

            if lt_data and isinstance(lt_data, dict):
                lthr = (lt_data.get('lactateThresholdHeartRate') or
                        lt_data.get('lactateThresholdHR') or
                        lt_data.get('thresholdHeartRate') or
                        lt_data.get('lthr'))
                if lthr:
                    logger.info(f"LTHR из Garmin: {lthr} уд/мин")
                    return int(lthr)

            try:
                max_metrics = self.client.get_max_metrics(date.today().isoformat())
                if max_metrics and isinstance(max_metrics, dict):
                    threshold = max_metrics.get('lactateThresholdHeartRate')
                    if threshold:
                        logger.info(f"LTHR из max_metrics: {threshold} уд/мин")
                        return int(threshold)
            except Exception as e:
                logger.info(f"get_max_metrics недоступен: {e}")

            return None

        except Exception as e:
            logger.warning(f"Не удалось получить LTHR: {e}")
            return None

    def get_personal_records(self) -> Dict[str, Dict[str, Any]]:
        """
        Получить персональные рекорды из Garmin.

        Returns:
            Словарь рекордов: {"5k": {"time_seconds": 1500, "date": "2024-01-15"}, ...}
        """
        if not self.client:
            if not self.login():
                return {}

        try:
            pr_data = self.client.get_personal_record()

            records = {}
            if pr_data and isinstance(pr_data, list):
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
                    our_type = distance_mapping.get(record_type)
                    if not our_type:
                        for garmin_key, our_key in distance_mapping.items():
                            if garmin_key in record_type.upper():
                                our_type = our_key
                                break

                    if our_type:
                        time_seconds = record.get('elapsedTime') or record.get('value')
                        if time_seconds:
                            if time_seconds > 86400:  # миллисекунды → секунды
                                time_seconds = time_seconds / 1000
                            record_date = record.get('prDate') or record.get('activityStartDateLocal')
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
        Синхронизация тренировок за последние 60 дней + LTHR + Personal Records.

        Returns:
            Tuple (количество тренировок, LTHR, personal_records)
        """
        logger.info(f"Начинаю синхронизацию 60 дней для user_id={user_id}")

        lthr = self.get_lactate_threshold()
        lthr_source = "garmin" if lthr else None

        personal_records = self.get_personal_records()

        total_saved = 0
        today = date.today()

        for days_ago in range(60):
            target_date = today - timedelta(days=days_ago)
            saved = self.sync_date(user_id, target_date)
            total_saved += saved

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
        Оценка LTHR по max HR из тренировок (fallback).

        Формула: LTHR ≈ 85% от max HR (Joe Friel)
        """
        trainings = db.get_user_trainings(user_id, limit=60)
        if not trainings:
            return None

        max_hrs = [t.max_hr for t in trainings if t.max_hr and t.max_hr > 100]
        if not max_hrs:
            return None

        max_hr = max(max_hrs)
        lthr = int(max_hr * 0.85)
        logger.info(f"LTHR рассчитан по max HR: {lthr} уд/мин (max HR={max_hr})")
        return lthr

    def sync_today(self, user_id: int) -> int:
        """Синхронизация тренировок за сегодня"""
        today = date.today()
        return self.sync_date(user_id, today)

    def sync_date(self, user_id: int, target_date: date) -> int:
        """
        Синхронизация тренировок за конкретную дату.

        Returns:
            Количество сохранённых тренировок
        """
        activities = self.get_activities_for_date(target_date)

        if not activities:
            return 0

        saved_count = 0

        with db.get_session() as session:
            for activity in activities:
                parsed = self.parse_activity(activity)

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
        Синхронизация тренировок для конкретного пользователя с его credentials.

        Returns:
            Количество сохранённых тренировок
        """
        credentials = db.get_user_garmin_credentials(user_id)

        if not credentials:
            logger.warning(f"Нет учетных данных Garmin для пользователя {user_id}")
            return 0

        email, password = credentials

        if not self.login(email, password):
            logger.error(f"Не удалось авторизоваться в Garmin для пользователя {user_id}")
            return 0

        return self.sync_date(user_id, target_date)


# Глобальный экземпляр
garmin_sync = GarminSync()
