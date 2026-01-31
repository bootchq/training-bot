"""Интеграция с Google Calendar API через OAuth"""
import os
from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import Dict
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from ..database.db import TrainingPlan
from ..database.db import db
from ..utils.config import Config
from ..utils.logger import logger

# Области доступа для Calendar API
SCOPES = ['https://www.googleapis.com/auth/calendar.events']


class GoogleCalendarAPI:
    """Интеграция с Google Calendar через OAuth"""

    def __init__(self):
        """Инициализация"""
        self.credentials_path = Config.GOOGLE_CREDENTIALS_PATH
        self.calendar_id = 'primary'

    def get_auth_url(self) -> str:
        """
        Получить URL для OAuth авторизации (для локального запуска)

        Returns:
            URL или инструкция
        """
        return (
            "Для подключения Google Calendar:\n\n"
            "1. Запусти локально: python -m bot_trainer.scripts.google_auth\n"
            "2. Авторизуйся в браузере\n"
            "3. Скопируй refresh_token и введи команду /set_google_token <token>"
        )

    def authorize_local(self) -> Optional[str]:
        """
        Локальная авторизация через браузер (для получения refresh_token)

        Returns:
            Refresh token для сохранения
        """
        if not os.path.exists(self.credentials_path):
            logger.error(f"❌ Файл credentials не найден: {self.credentials_path}")
            return None

        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                self.credentials_path, SCOPES
            )
            creds = flow.run_local_server(port=8080)

            logger.info("✅ Авторизация Google Calendar успешна")
            return creds.refresh_token

        except Exception as e:
            logger.error(f"❌ Ошибка авторизации Google: {e}")
            return None

    def get_service(self, user_id: int):
        """
        Получить Google Calendar service для пользователя

        Args:
            user_id: ID пользователя

        Returns:
            Google Calendar service или None
        """
        refresh_token = db.get_user_google_credentials(user_id)
        if not refresh_token:
            return None

        try:
            # Читаем client_id и client_secret из credentials.json
            import json
            with open(self.credentials_path) as f:
                creds_data = json.load(f)

            if 'installed' in creds_data:
                client_config = creds_data['installed']
            elif 'web' in creds_data:
                client_config = creds_data['web']
            else:
                logger.error("Неверный формат credentials.json")
                return None

            creds = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri='https://oauth2.googleapis.com/token',
                client_id=client_config['client_id'],
                client_secret=client_config['client_secret'],
                scopes=SCOPES
            )

            # Обновляем токен если нужно
            if not creds.valid:
                creds.refresh(Request())

            return build('calendar', 'v3', credentials=creds)

        except Exception as e:
            logger.error(f"❌ Ошибка получения Google Calendar service: {e}")
            return None

    def sync_training_plan(self, user_id: int, start_date=None, weeks: int = 2) -> int:
        """
        Синхронизировать план тренировок с Google Calendar

        Args:
            user_id: ID пользователя
            start_date: Начальная дата (по умолчанию - начало текущей недели)
            weeks: Количество недель

        Returns:
            Количество созданных событий
        """
        service = self.get_service(user_id)
        if not service:
            logger.warning(f"Google Calendar не подключён для user_id={user_id}")
            return 0

        if not start_date:
            today = datetime.now().date()
            start_date = today - timedelta(days=today.weekday())

        end_date = start_date + timedelta(weeks=weeks)

        # Получаем план тренировок
        plans = db.get_plan_for_week(user_id, start_date)

        synced = 0
        for plan in plans:
            if plan.date > end_date:
                continue

            event = self._create_calendar_event(plan)
            if event:
                try:
                    service.events().insert(calendarId=self.calendar_id, body=event).execute()
                    synced += 1
                except Exception as e:
                    logger.error(f"Ошибка создания события: {e}")

        logger.info(f"Синхронизировано {synced} тренировок в Google Calendar для user_id={user_id}")
        return synced

    def _create_calendar_event(self, plan: TrainingPlan) -> Dict[str, Any]:
        """
        Создать событие календаря из плана тренировки

        Args:
            plan: План тренировки

        Returns:
            Словарь события для Google Calendar API
        """
        # Время тренировки (утро 07:00)
        start_time = datetime.combine(plan.date, datetime.min.time().replace(hour=7))
        duration_min = plan.duration_min or 60
        end_time = start_time + timedelta(minutes=duration_min)

        # Описание
        description = f"Тип: {plan.type}\n"
        if plan.distance_km:
            description += f"Дистанция: {plan.distance_km:.1f} км\n"
        if plan.target_zone:
            description += f"Зоны: {plan.target_zone}\n"
        if plan.description:
            description += f"\n{plan.description}"

        return {
            'summary': f"🏃 {plan.type}",
            'description': description,
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'Europe/Moscow',
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'Europe/Moscow',
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': 60},  # За 1 час
                    {'method': 'popup', 'minutes': 15},  # За 15 минут
                ],
            },
        }


# Глобальный экземпляр
google_calendar_api = GoogleCalendarAPI()
