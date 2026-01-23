"""Тестирование Garmin-интеграции"""
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent))

from src.utils.logger import logger
from src.database.init_db import init_database
from src.database.db import db
from src.integrations.garmin_sync import garmin_sync


def test_sync():
    """Тест синхронизации"""
    logger.info("=" * 50)
    logger.info("🧪 Тестирование Garmin-интеграции")
    logger.info("=" * 50)

    # Инициализация БД
    if not init_database():
        logger.error("Не удалось инициализировать БД")
        return

    # Создание тестового пользователя
    test_telegram_id = 123456789
    user = db.get_or_create_user(test_telegram_id)
    logger.info(f"Тестовый пользователь: ID={user.id}, Telegram={test_telegram_id}")

    # Синхронизация за сегодня
    logger.info("\n📥 Синхронизация тренировок за сегодня...")
    count = garmin_sync.sync_today(user.id)

    if count > 0:
        logger.info(f"✅ Сохранено {count} тренировок")
    else:
        logger.info("ℹ️  Тренировок за сегодня нет")

    logger.info("=" * 50)
    logger.info("✅ Тест завершён")
    logger.info("=" * 50)


if __name__ == "__main__":
    test_sync()
