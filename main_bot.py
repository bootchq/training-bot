"""
Service 1: Коммуникация с пользователем (front_kommunikaciya_s_polzovatelem)

Только синхронные ответы на команды пользователя:
- Telegram polling
- Команды /start, /sync, /stats, /plan
- Callback кнопки
- ConversationHandler (онбординг)

НЕ делает: анализ тренировок, schedulers, проверку Garmin
"""
import asyncio
import os
import sys
from pathlib import Path

# Добавляем корневую папку в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from telegram import Update

from src.bot.telegram_bot import TrainingBot
from src.database.init_db import init_database
from src.utils.health_check import health_server
from src.utils.logger import logger


async def run_bot():
    """Запуск Telegram бота"""
    bot = None
    try:
        # Запускаем health check сервер
        await health_server.start()

        logger.info("🤖 Запуск Service 1: Коммуникация с пользователем")

        # Запускаем бота
        bot = TrainingBot()

        logger.info("✅ Бот запущен")

        # Запускаем polling (блокирующий вызов)
        await bot.app.initialize()
        await bot.app.start()

        # Инициализируем после start
        await bot.register_commands()
        logger.info("✅ Команды зарегистрированы")

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
    logger.info("🏃 Запуск Service 1: Коммуникация")
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
        asyncio.run(run_bot())
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
