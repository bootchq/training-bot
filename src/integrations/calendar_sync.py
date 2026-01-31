"""Синхронизация с Google Calendar и генерация ICS файлов"""
import pickle
import uuid
from datetime import date
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Any
from typing import Dict
from typing import Optional

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from icalendar import Calendar
from icalendar import Event

from ..database.db import TrainingPlan
from ..database.db import db
from ..utils.config import Config
from ..utils.logger import logger

# Права доступа к календарю
SCOPES = ['https://www.googleapis.com/auth/calendar']


class CalendarSync:
    """Синхронизация плана тренировок с Google Calendar"""

    def __init__(self):
        """Инициализация синхронизатора"""
        self.creds = None
        self.service = None
        self.token_path = Path(Config.DATA_DIR) / 'token.pickle'
        self.credentials_path = Path(Config.DATA_DIR) / 'credentials.json'

    def authenticate(self) -> bool:
        """
        OAuth авторизация в Google Calendar

        Returns:
            True если авторизация успешна
        """
        # Загружаем токен из файла если он есть
        if self.token_path.exists():
            with open(self.token_path, 'rb') as token:
                self.creds = pickle.load(token)

        # Если токен невалидный или истёк
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                # Обновляем токен
                try:
                    self.creds.refresh(Request())
                    logger.info("Google Calendar токен обновлён")
                except Exception as e:
                    logger.error(f"Ошибка обновления токена: {e}")
                    self.creds = None

            # Если всё ещё нет валидного токена - новая авторизация
            if not self.creds:
                if not self.credentials_path.exists():
                    logger.error(
                        f"Файл credentials.json не найден: {self.credentials_path}\n"
                        "Создайте проект в Google Cloud Console и скачайте credentials.json"
                    )
                    return False

                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.credentials_path), SCOPES
                    )
                    self.creds = flow.run_local_server(port=0)
                    logger.info("Google Calendar авторизация успешна")
                except Exception as e:
                    logger.error(f"Ошибка авторизации: {e}")
                    return False

            # Сохраняем токен
            with open(self.token_path, 'wb') as token:
                pickle.dump(self.creds, token)

        # Создаём сервис
        try:
            self.service = build('calendar', 'v3', credentials=self.creds)
            logger.info("Google Calendar API подключён")
            return True
        except Exception as e:
            logger.error(f"Ошибка создания сервиса: {e}")
            return False

    def create_event(
        self,
        summary: str,
        description: str,
        start_date: date,
        duration_min: int = 60,
        calendar_id: str = 'primary'
    ) -> Optional[str]:
        """
        Создать событие в календаре

        Args:
            summary: Название события
            description: Описание
            start_date: Дата тренировки
            duration_min: Длительность в минутах
            calendar_id: ID календаря (по умолчанию основной)

        Returns:
            ID события или None
        """
        if not self.service:
            if not self.authenticate():
                return None

        # Время начала (предполагаем 19:00)
        start_time = datetime.combine(start_date, datetime.min.time().replace(hour=19, minute=0))
        end_time = start_time + timedelta(minutes=duration_min)

        event = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'Europe/Moscow',
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'Europe/Moscow',
            },
            'colorId': '9',  # Синий цвет для тренировок
        }

        try:
            created_event = self.service.events().insert(
                calendarId=calendar_id,
                body=event
            ).execute()

            logger.info(f"Событие создано: {summary} на {start_date}")
            return created_event.get('id')

        except HttpError as e:
            logger.error(f"Ошибка создания события: {e}")
            return None

    def update_event(
        self,
        event_id: str,
        summary: str = None,
        description: str = None,
        start_date: date = None,
        duration_min: int = None,
        color_id: str = None,
        calendar_id: str = 'primary'
    ) -> bool:
        """
        Обновить событие в календаре

        Args:
            event_id: ID события
            summary: Новое название
            description: Новое описание
            start_date: Новая дата
            duration_min: Новая длительность
            color_id: ID цвета (например '8' для серого)
            calendar_id: ID календаря

        Returns:
            True если успешно
        """
        if not self.service:
            if not self.authenticate():
                return False

        try:
            # Получаем существующее событие
            event = self.service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()

            # Обновляем поля
            if summary:
                event['summary'] = summary
            if description:
                event['description'] = description
            if color_id:
                event['colorId'] = color_id

            if start_date and duration_min:
                start_time = datetime.combine(start_date, datetime.min.time().replace(hour=19, minute=0))
                end_time = start_time + timedelta(minutes=duration_min)

                event['start'] = {
                    'dateTime': start_time.isoformat(),
                    'timeZone': 'Europe/Moscow',
                }
                event['end'] = {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'Europe/Moscow',
                }

            # Сохраняем
            self.service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event
            ).execute()

            logger.info(f"Событие обновлено: {event_id}")
            return True

        except HttpError as e:
            logger.error(f"Ошибка обновления события: {e}")
            return False

    def delete_event(self, event_id: str, calendar_id: str = 'primary') -> bool:
        """
        Удалить событие из календаря

        Args:
            event_id: ID события
            calendar_id: ID календаря

        Returns:
            True если успешно
        """
        if not self.service:
            if not self.authenticate():
                return False

        try:
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()

            logger.info(f"Событие удалено: {event_id}")
            return True

        except HttpError as e:
            logger.error(f"Ошибка удаления события: {e}")
            return False

    def sync_weekly_plan(self, user_id: int, start_date: date) -> Dict[str, Any]:
        """
        Синхронизация плана на неделю с Google Calendar

        Args:
            user_id: ID пользователя
            start_date: Начало недели

        Returns:
            Статистика синхронизации
        """
        if not self.service:
            if not self.authenticate():
                return {'success': False, 'error': 'Не удалось авторизоваться'}

        # Получаем план на неделю
        plans = db.get_plan_for_week(user_id, start_date)

        if not plans:
            return {'success': False, 'error': 'План не найден'}

        created = 0
        updated = 0
        errors = 0

        for plan in plans:
            # Формируем название и описание
            summary = self._format_event_summary(plan)
            description = self._format_event_description(plan)

            # Создаём событие
            event_id = self.create_event(
                summary=summary,
                description=description,
                start_date=plan.date,
                duration_min=plan.duration_min or 60
            )

            if event_id:
                created += 1
            else:
                errors += 1

        logger.info(f"Синхронизация завершена: создано {created}, ошибок {errors}")

        return {
            'success': True,
            'created': created,
            'updated': updated,
            'errors': errors
        }

    def _format_event_summary(self, plan: TrainingPlan) -> str:
        """Форматирование названия события"""
        type_names = {
            'easy': 'Лёгкая пробежка',
            'tempo': 'Темповая',
            'intervals': 'Интервалы',
            'long': 'Длинная',
            'recovery': 'Восстановительная',
        }

        name = type_names.get(plan.type, plan.type.upper())

        if plan.distance_km:
            return f"🏃 {name} ({plan.distance_km:.0f}км)"
        elif plan.duration_min:
            return f"🏃 {name} ({plan.duration_min}мин)"
        else:
            return f"🏃 {name}"

    def _format_event_description(self, plan: TrainingPlan) -> str:
        """Форматирование описания события"""
        lines = []

        if plan.target_zone:
            lines.append(f"Целевая зона: {plan.target_zone}")

        if plan.distance_km:
            lines.append(f"Дистанция: {plan.distance_km:.1f} км")

        if plan.duration_min:
            lines.append(f"Длительность: {plan.duration_min} мин")

        if plan.description:
            lines.append(f"\n{plan.description}")

        lines.append("\n📱 Бот тренера")

        return "\n".join(lines)

    def generate_ics_file(self, user_id: int, start_date: date, weeks: int = 1) -> Optional[str]:
        """
        Генерация ICS файла для импорта в iPhone Calendar

        Best practice: UID uppercase для iOS, корректные timezone
        Источник: discussions.apple.com/thread/255910569

        Args:
            user_id: ID пользователя
            start_date: Начало периода
            weeks: Количество недель (по умолчанию 1)

        Returns:
            Путь к созданному ICS файлу или None
        """
        # Получаем план на указанный период
        end_date = start_date + timedelta(weeks=weeks)
        plans = db.get_plan_for_period(user_id, start_date, end_date)

        if not plans:
            logger.warning(f"План не найден для пользователя {user_id}")
            return None

        # Создаём календарь
        cal = Calendar()
        cal.add('prodid', '-//Training Bot//Adaptive Running Plan//RU')
        cal.add('version', '2.0')
        cal.add('calscale', 'GREGORIAN')
        cal.add('method', 'PUBLISH')
        cal.add('x-wr-calname', 'План тренировок')
        cal.add('x-wr-timezone', 'Europe/Moscow')
        cal.add('x-wr-caldesc', 'Адаптивный план тренировок по бегу')

        # Добавляем события
        for plan in plans:
            event = Event()

            # UID в uppercase для iOS (best practice)
            event.add('uid', str(uuid.uuid4()).upper())

            # Название события
            summary = self._format_event_summary(plan)
            event.add('summary', summary)

            # Описание
            description = self._format_event_description(plan)
            event.add('description', description)

            # Время начала и конца (по умолчанию 19:00)
            start_time = datetime.combine(plan.date, datetime.min.time().replace(hour=19, minute=0))
            duration = plan.duration_min or 60
            end_time = start_time + timedelta(minutes=duration)

            # Добавляем время с timezone (важно для iOS)
            event.add('dtstart', start_time)
            event.add('dtstamp', datetime.now())
            event.add('dtend', end_time)

            # Локация (опционально)
            if plan.target_zone:
                event.add('location', f"Целевая зона: {plan.target_zone}")

            # Категория
            event.add('categories', ['Спорт', 'Бег', 'Тренировка'])

            # Статус
            event.add('status', 'CONFIRMED')

            # Приоритет (важные тренировки - высокий приоритет)
            if plan.type in ['tempo', 'intervals', 'long']:
                event.add('priority', 5)  # Высокий приоритет
            else:
                event.add('priority', 0)  # Обычный приоритет

            cal.add_component(event)

        # Сохраняем файл
        ics_path = Path(Config.DATA_DIR) / f'training_plan_{start_date.strftime("%Y%m%d")}.ics'

        try:
            with open(ics_path, 'wb') as f:
                f.write(cal.to_ical())

            logger.info(f"ICS файл создан: {ics_path}")
            return str(ics_path)

        except Exception as e:
            logger.error(f"Ошибка создания ICS файла: {e}")
            return None


# Глобальный экземпляр
calendar_sync = CalendarSync()
