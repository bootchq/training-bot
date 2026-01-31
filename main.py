"""Точка входа приложения"""
import sys
import os
import asyncio
from pathlib import Path

# КРИТИЧНО: Устанавливаем таймзону MSK для всего приложения
os.environ['TZ'] = 'Europe/Moscow'

# Добавляем корневую папку в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.logger import logger
from src.utils.health_check import health_server
from src.database.init_db import init_database
from src.bot.telegram_bot import TrainingBot
from telegram import Update


async def run_all():
    """Запуск бота и health check сервера в одном event loop"""
    bot = None
    try:
        # Запускаем health check сервер
        await health_server.start()

        # Запускаем бота
        bot = TrainingBot()

        logger.info("🚀 Бот запущен")

        # Запускаем polling (блокирующий вызов)
        await bot.app.initialize()
        await bot.app.start()

        # Инициализируем после start
        await bot.register_commands()
        from src.core.reminders import init_reminder_scheduler
        bot.reminder_scheduler = init_reminder_scheduler(bot.send_notification_message)
        logger.info("✅ Планировщик напоминаний инициализирован")

        await bot.app.updater.start_polling(allowed_updates=Update.ALL_TYPES)

        # Держим бота запущенным
        try:
            await asyncio.Event().wait()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Получен сигнал остановки")

    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        raise
    finally:
        # Останавливаем бота
        if bot:
            try:
                bot.stop()
            except Exception as e:
                logger.error(f"Ошибка остановки бота: {e}")

        # Останавливаем health check сервер
        try:
            await health_server.stop()
        except Exception as e:
            logger.error(f"Ошибка остановки health check: {e}")


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
        asyncio.run(run_all())
    except KeyboardInterrupt:
        logger.info("Остановка бота (Ctrl+C)")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
    finally:
        logger.info("=" * 50)
        logger.info("👋 Бот остановлен")
        logger.info("=" * 50)


if __name__ == "__main__":
    main()
