"""Интеграция со Strava API"""
import time
from datetime import date
from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import requests

from ..database.db import Training
from ..database.db import db
from ..utils.config import Config
from ..utils.logger import logger


class StravaSync:
    """Синхронизация со Strava"""

    AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
    TOKEN_URL = "https://www.strava.com/oauth/token"
    API_URL = "https://www.strava.com/api/v3"

    def __init__(self):
        """Инициализация"""
        self.client_id = Config.STRAVA_CLIENT_ID
        self.client_secret = Config.STRAVA_CLIENT_SECRET
        self.redirect_uri = Config.STRAVA_REDIRECT_URI

    def get_auth_url(self, user_id: int) -> str:
        """
        Получить URL для авторизации пользователя

        Args:
            user_id: ID пользователя в БД (для state)

        Returns:
            URL для авторизации в Strava
        """
        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'scope': 'read,activity:read_all',
            'state': str(user_id)  # Для идентификации пользователя при callback
        }

        query = '&'.join([f'{k}={v}' for k, v in params.items()])
        return f"{self.AUTHORIZE_URL}?{query}"

    def exchange_code_for_token(self, code: str) -> Optional[Dict[str, Any]]:
        """
        Обменять код авторизации на токены

        Args:
            code: Код авторизации от Strava

        Returns:
            Словарь с токенами или None при ошибке
        """
        try:
            response = requests.post(self.TOKEN_URL, data={
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'code': code,
                'grant_type': 'authorization_code'
            })

            if response.status_code == 200:
                data = response.json()
                logger.info("✅ Получены токены Strava")
                return {
                    'access_token': data['access_token'],
                    'refresh_token': data['refresh_token'],
                    'expires_at': data['expires_at']
                }
            else:
                logger.error(f"❌ Ошибка обмена кода: {response.text}")
                return None

        except Exception as e:
            logger.error(f"❌ Ошибка при обмене кода Strava: {e}")
            return None

    def refresh_access_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """
        Обновить access_token используя refresh_token

        Args:
            refresh_token: Refresh token

        Returns:
            Новые токены или None при ошибке
        """
        try:
            response = requests.post(self.TOKEN_URL, data={
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token'
            })

            if response.status_code == 200:
                data = response.json()
                logger.info("✅ Токен Strava обновлён")
                return {
                    'access_token': data['access_token'],
                    'refresh_token': data['refresh_token'],
                    'expires_at': data['expires_at']
                }
            else:
                logger.error(f"❌ Ошибка обновления токена: {response.text}")
                return None

        except Exception as e:
            logger.error(f"❌ Ошибка обновления токена Strava: {e}")
            return None

    def get_valid_token(self, user_id: int) -> Optional[str]:
        """
        Получить действующий access_token для пользователя

        Args:
            user_id: ID пользователя

        Returns:
            Access token или None если нет/невалидный
        """
        creds = db.get_user_strava_credentials(user_id)
        if not creds:
            return None

        access_token, refresh_token, expires_at = creds

        # Проверяем срок действия (с запасом 5 минут)
        if expires_at and expires_at > time.time() + 300:
            return access_token

        # Токен истёк - обновляем
        if refresh_token:
            new_tokens = self.refresh_access_token(refresh_token)
            if new_tokens:
                db.save_user_strava_credentials(
                    user_id,
                    new_tokens['access_token'],
                    new_tokens['refresh_token'],
                    new_tokens['expires_at']
                )
                return new_tokens['access_token']

        return None

    def get_activities(self, access_token: str, after: date = None, before: date = None) -> List[Dict[str, Any]]:
        """
        Получить список активностей

        Args:
            access_token: Access token
            after: Дата начала (опционально)
            before: Дата конца (опционально)

        Returns:
            Список активностей
        """
        try:
            headers = {'Authorization': f'Bearer {access_token}'}
            params = {'per_page': 30}

            if after:
                params['after'] = int(datetime.combine(after, datetime.min.time()).timestamp())
            if before:
                params['before'] = int(datetime.combine(before, datetime.max.time()).timestamp())

            response = requests.get(
                f"{self.API_URL}/athlete/activities",
                headers=headers,
                params=params
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"❌ Ошибка получения активностей: {response.text}")
                return []

        except Exception as e:
            logger.error(f"❌ Ошибка Strava API: {e}")
            return []

    def sync_activities_for_user(self, user_id: int, days: int = 7) -> int:
        """
        Синхронизировать активности пользователя

        Args:
            user_id: ID пользователя
            days: За сколько дней синхронизировать

        Returns:
            Количество синхронизированных тренировок
        """
        access_token = self.get_valid_token(user_id)
        if not access_token:
            logger.warning(f"Нет действующего токена Strava для user_id={user_id}")
            return 0

        after_date = date.today() - timedelta(days=days)
        activities = self.get_activities(access_token, after=after_date)

        synced = 0
        for activity in activities:
            # Только беговые активности
            if activity.get('type') not in ['Run', 'TrailRun', 'VirtualRun']:
                continue

            training = self._convert_activity_to_training(activity, user_id)
            if training:
                db.save_training(training)
                synced += 1

        logger.info(f"Синхронизировано {synced} тренировок из Strava для user_id={user_id}")
        return synced

    def _convert_activity_to_training(self, activity: Dict[str, Any], user_id: int) -> Optional[Training]:
        """
        Конвертировать активность Strava в Training

        Args:
            activity: Данные активности от Strava
            user_id: ID пользователя

        Returns:
            Объект Training
        """
        try:
            # Парсим дату
            start_date_str = activity.get('start_date_local', '')
            if start_date_str:
                activity_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00')).date()
            else:
                return None

            # Расстояние в км
            distance_km = activity.get('distance', 0) / 1000

            # Время в минутах
            duration_min = activity.get('moving_time', 0) // 60

            # Средний темп (мин/км)
            avg_pace = None
            if distance_km > 0 and duration_min > 0:
                pace_seconds = (duration_min * 60) / distance_km
                pace_min = int(pace_seconds // 60)
                pace_sec = int(pace_seconds % 60)
                avg_pace = f"{pace_min}:{pace_sec:02d}"

            # Пульс
            avg_hr = activity.get('average_heartrate')
            max_hr = activity.get('max_heartrate')

            # Набор высоты
            elevation_m = activity.get('total_elevation_gain')

            training = Training(
                user_id=user_id,
                date=activity_date,
                type='actual',
                distance_km=round(distance_km, 2),
                duration_min=duration_min,
                avg_pace=avg_pace,
                avg_hr=int(avg_hr) if avg_hr else None,
                max_hr=int(max_hr) if max_hr else None,
                elevation_m=int(elevation_m) if elevation_m else None,
                notes=f"Strava: {activity.get('name', '')}"
            )

            return training

        except Exception as e:
            logger.error(f"Ошибка конвертации активности Strava: {e}")
            return None


# Глобальный экземпляр
strava_sync = StravaSync()
