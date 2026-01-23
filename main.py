"""Точка входа приложения"""
import sys
import os
import asyncio
from pathlib import Path

# Добавляем корневую папку в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.logger import logger
from src.utils.health_check import health_server
from src.database.init_db import init_database
from src.bot.telegram_bot import TrainingBot


async def run_bot():
    """Запуск бота в async режиме"""
    bot = TrainingBot()
    await bot.run_async()


def main():
    """Основная функция"""
    logger.info("=" * 50)
    logger.info("🏃 Запуск бота-тренера")
    logger.info("=" * 50)

    # Инициализация БД
    if not init_database():
        logger.error("Не удалось инициализировать БД. Выход.")
        return

    # Получаем порт из переменной окружения (Railway)
    port = int(os.getenv('PORT', 8080))
    health_server.port = port

    # Запуск бота и health check сервера
    try:
        # Создаём event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Запускаем health check сервер
        loop.run_until_complete(health_server.start())

        # Запускаем бота (синхронный метод)
        bot = TrainingBot()
        bot.run()

    except KeyboardInterrupt:
        logger.info("Остановка бота (Ctrl+C)")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
    finally:
        # Останавливаем health check сервер
        try:
            loop.run_until_complete(health_server.stop())
        except:
            pass

        logger.info("=" * 50)
        logger.info("👋 Бот остановлен")
        logger.info("=" * 50)


if __name__ == "__main__":
    main()
