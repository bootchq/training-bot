"""Health check HTTP сервер для Railway + ICS календарь подписка"""
import asyncio
from aiohttp import web
from datetime import datetime, timedelta
from typing import Optional
import uuid

from .logger import logger


class HealthCheckServer:
    """HTTP сервер для health check и ICS календаря"""

    def __init__(self, port: int = 8080):
        """
        Инициализация сервера

        Args:
            port: Порт для HTTP сервера (Railway использует PORT env variable)
        """
        self.port = port
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None

        # Добавляем routes
        self.app.router.add_get('/', self.health_check)
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/calendar/{token}.ics', self.serve_ics)

        # Время запуска
        self.start_time = datetime.now()

    async def health_check(self, request):
        """
        Health check endpoint

        Возвращает:
            200 OK с информацией о статусе бота
        """
        uptime = datetime.now() - self.start_time

        response_data = {
            'status': 'healthy',
            'service': 'training-bot',
            'uptime_seconds': int(uptime.total_seconds()),
            'timestamp': datetime.now().isoformat()
        }

        return web.json_response(response_data)

    async def serve_ics(self, request):
        """
        ICS календарь подписка

        URL: /calendar/{token}.ics
        Возвращает ICS файл с планом тренировок на 4 недели
        """
        token = request.match_info.get('token')

        if not token:
            return web.Response(status=400, text='Missing token')

        try:
            # Импортируем здесь чтобы избежать циклических импортов
            from ..database.db import db
            from icalendar import Calendar, Event

            # Находим пользователя по токену
            user = db.get_user_by_calendar_token(token)

            if not user:
                logger.warning(f"ICS запрос с неверным токеном: {token[:8]}...")
                return web.Response(status=404, text='Calendar not found')

            # Получаем план на 4 недели вперёд
            today = datetime.now().date()
            start_of_week = today - timedelta(days=today.weekday())
            end_date = start_of_week + timedelta(weeks=4)

            plans = db.get_plan_for_period(user.id, start_of_week, end_date)

            # Создаём ICS календарь
            cal = Calendar()
            cal.add('prodid', '-//Training Bot//План тренировок//RU')
            cal.add('version', '2.0')
            cal.add('calscale', 'GREGORIAN')
            cal.add('method', 'PUBLISH')
            cal.add('x-wr-calname', 'План тренировок')
            cal.add('x-wr-timezone', 'Europe/Moscow')
            cal.add('refresh-interval;value=duration', 'P1D')  # Обновлять раз в день

            # Добавляем события
            for plan in plans:
                event = Event()

                # UID стабильный для каждой тренировки (чтобы обновления работали)
                event.add('uid', f"training-{user.id}-{plan.date.isoformat()}@bot")

                # Название
                emoji_map = {
                    'длинная': '🏃‍♂️', 'интервалы': '⚡', 'темповый': '🔥',
                    'восстановительная': '🧘', 'кросс': '🌲', 'легкая': '😊'
                }
                workout_type = plan.type.lower()
                emoji = '🏃'
                for key, e in emoji_map.items():
                    if key in workout_type:
                        emoji = e
                        break

                summary = f"{emoji} {plan.type.upper()}"
                if plan.distance_km:
                    summary += f" ({plan.distance_km:.0f}км)"
                elif plan.duration_min:
                    summary += f" ({plan.duration_min}мин)"

                event.add('summary', summary)

                # Описание
                desc_parts = []
                if plan.target_zone:
                    desc_parts.append(f"Зона: {plan.target_zone}")
                if plan.distance_km:
                    desc_parts.append(f"Дистанция: {plan.distance_km:.1f} км")
                if plan.duration_min:
                    desc_parts.append(f"Время: {plan.duration_min} мин")
                if plan.description:
                    desc_parts.append(f"\n{plan.description}")
                desc_parts.append("\n📱 Бот тренера")

                event.add('description', '\n'.join(desc_parts))

                # Время (19:00 по умолчанию)
                start_time = datetime.combine(plan.date, datetime.min.time().replace(hour=19, minute=0))
                duration = plan.duration_min or 60
                end_time = start_time + timedelta(minutes=duration)

                event.add('dtstart', start_time)
                event.add('dtend', end_time)
                event.add('dtstamp', datetime.now())

                # Напоминание за 1 час
                from icalendar import Alarm
                alarm = Alarm()
                alarm.add('action', 'DISPLAY')
                alarm.add('trigger', timedelta(hours=-1))
                alarm.add('description', f'Тренировка через час: {plan.type}')
                event.add_component(alarm)

                cal.add_component(event)

            # Возвращаем ICS
            ics_content = cal.to_ical()

            logger.info(f"ICS отдан для user_id={user.id}, событий: {len(plans)}")

            return web.Response(
                body=ics_content,
                content_type='text/calendar; charset=utf-8',
                headers={
                    'Content-Disposition': 'inline; filename="training.ics"',
                    'Cache-Control': 'no-cache, no-store, must-revalidate'
                }
            )

        except Exception as e:
            logger.error(f"Ошибка генерации ICS: {e}", exc_info=True)
            return web.Response(status=500, text='Internal error')

    async def start(self):
        """Запуск HTTP сервера"""
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()

            self.site = web.TCPSite(self.runner, '0.0.0.0', self.port)
            await self.site.start()

            logger.info(f"✅ HTTP сервер запущен на порту {self.port}")
            logger.info(f"   Endpoints: /, /health, /calendar/{{token}}.ics")

        except Exception as e:
            logger.error(f"Ошибка запуска HTTP сервера: {e}")
            raise

    async def stop(self):
        """Остановка HTTP сервера"""
        try:
            if self.site:
                await self.site.stop()
            if self.runner:
                await self.runner.cleanup()
            logger.info("HTTP сервер остановлен")
        except Exception as e:
            logger.error(f"Ошибка остановки HTTP сервера: {e}")


# Глобальный экземпляр
health_server = HealthCheckServer()
