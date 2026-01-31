"""Инициализация базы данных"""
from .db import db
from .db import logger


def init_database():
    """Создание таблиц БД"""
    try:
        db.create_tables()
        logger.info("✅ База данных инициализирована")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")
        return False


if __name__ == "__main__":
    init_database()
