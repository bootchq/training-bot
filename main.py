"""Точка входа приложения"""
# КРИТИЧНО: Устанавливаем таймзону MSK ПЕРЕД всеми импортами
import os
import time

os.environ['TZ'] = 'Europe/Moscow'
time.tzset()

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from telegram import Update
from telegram.ext import Application

from src.bot.telegram_bot import TrainingBot
from src.database.init_db import init_database
from src.utils.config import Config
from src.utils.health_check import health_server
from src.utils.logger import logger


async def run_polling(bot: TrainingBot):
    """Режим polling — для локальной разработки"""
    await bot.app.initialize()
    await bot.app.start()

    await bot.register_commands()
    from src.core.reminders import init_reminder_scheduler
    bot.reminder_scheduler = init_reminder_scheduler(bot.send_notification_message)
    logger.info("Планировщик напоминаний инициализирован")

    await bot.app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    logger.info("Polling запущен")

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Получен сигнал остановки")
    finally:
        await bot.app.updater.stop()
        await bot.app.stop()


async def run_webhook(bot: TrainingBot, webhook_url: str, port: int):
    """
    Режим webhook — для Railway деплоя.

    Преимущества перед polling:
    - Мгновенная доставка сообщений (нет задержки 15 сек)
    - Меньше CPU/RAM нагрузки (нет постоянных запросов к Telegram)
    - Один HTTP сервер вместо двух (webhook + health check)
    """
    webhook_path = f"/webhook/{Config.WEBHOOK_SECRET or 'bot'}"
    full_webhook_url = f"{webhook_url.rstrip('/')}{webhook_path}"

    await bot.app.initialize()
    await bot.app.start()

    await bot.register_commands()
    from src.core.reminders import init_reminder_scheduler
    bot.reminder_scheduler = init_reminder_scheduler(bot.send_notification_message)
    logger.info("Планировщик напоминаний инициализирован")

    await bot.app.bot.set_webhook(
        url=full_webhook_url,
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )
    logger.info(f"Webhook установлен: {full_webhook_url}")

    # Запускаем webhook сервер
    await bot.app.updater.start_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=webhook_path,
        webhook_url=full_webhook_url,
        secret_token=Config.WEBHOOK_SECRET
    )
    logger.info(f"Webhook сервер слушает на порту {port}")

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Получен сигнал остановки")
    finally:
        await bot.app.bot.delete_webhook()
        await bot.app.updater.stop()
        await bot.app.stop()


async def run_all():
    """Запуск бота — автовыбор режима по наличию WEBHOOK_URL"""
    bot = None
    try:
        # Запускаем health check сервер
        await health_server.start()

        bot = TrainingBot()

        logger.info("Бот запущен")

        webhook_url = Config.WEBHOOK_URL
        port = int(os.getenv('PORT', 8080))

        if webhook_url:
            logger.info(f"Режим: webhook ({webhook_url})")
            # При webhook health_server занял бы порт — останавливаем его
            # Telegram сам будет пинговать webhook endpoint
            await health_server.stop()
            await run_webhook(bot, webhook_url, port)
        else:
            logger.info("Режим: polling (WEBHOOK_URL не задан)")
            await run_polling(bot)

    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        raise
    finally:
        if bot:
            try:
                bot.stop()
            except Exception as e:
                logger.error(f"Ошибка остановки бота: {e}")
        try:
            await health_server.stop()
        except Exception:
            pass


def main():
    """Основная функция"""
    logger.info("=" * 50)
    logger.info("Запуск бота-тренера")
    logger.info("=" * 50)

    if not init_database():
        logger.error("Не удалось инициализировать БД. Выход.")
        return

    port = int(os.getenv('PORT', 8080))
    health_server.port = port

    try:
        asyncio.run(run_all())
    except KeyboardInterrupt:
        logger.info("Остановка бота (Ctrl+C)")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
    finally:
        logger.info("=" * 50)
        logger.info("Бот остановлен")
        logger.info("=" * 50)


if __name__ == "__main__":
    main()
