"""Health check HTTP сервер для Railway keep-alive"""
import asyncio
from aiohttp import web
from datetime import datetime
from typing import Optional

from .logger import logger


class HealthCheckServer:
    """HTTP сервер для health check endpoint"""

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

    async def start(self):
        """Запуск HTTP сервера"""
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()

            self.site = web.TCPSite(self.runner, '0.0.0.0', self.port)
            await self.site.start()

            logger.info(f"✅ Health check сервер запущен на порту {self.port}")
            logger.info(f"   Endpoints: http://0.0.0.0:{self.port}/ и /health")

        except Exception as e:
            logger.error(f"Ошибка запуска health check сервера: {e}")
            raise

    async def stop(self):
        """Остановка HTTP сервера"""
        try:
            if self.site:
                await self.site.stop()
            if self.runner:
                await self.runner.cleanup()
            logger.info("Health check сервер остановлен")
        except Exception as e:
            logger.error(f"Ошибка остановки health check сервера: {e}")


# Глобальный экземпляр
health_server = HealthCheckServer()
