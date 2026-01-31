#!/usr/bin/env python3
"""
Миграция данных из SQLite (volume) в PostgreSQL
"""
import os
import sys
from pathlib import Path

# Добавляем корневую папку в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from src.database.models import Base, User, Training, Goal, TrainingPlan, WellnessSurvey
from src.utils.logger import logger

def migrate_data():
    """Перенос данных из SQLite в PostgreSQL"""

    # SQLite source (старый volume)
    sqlite_path = os.getenv("SQLITE_PATH", "/data/training_bot.db")
    sqlite_url = f"sqlite:///{sqlite_path}"

    # PostgreSQL target (новая БД)
    postgres_url = os.getenv("DATABASE_URL")

    if not postgres_url:
        logger.error("DATABASE_URL не установлен!")
        return False

    # Конвертация для psycopg3
    if postgres_url.startswith("postgresql://"):
        postgres_url = postgres_url.replace("postgresql://", "postgresql+psycopg://", 1)

    logger.info("=" * 60)
    logger.info("🔄 Миграция SQLite → PostgreSQL")
    logger.info("=" * 60)

    # Подключение к обеим БД
    logger.info(f"📂 SQLite: {sqlite_path}")
    logger.info(f"🐘 PostgreSQL: {postgres_url[:50]}...")

    try:
        # Создаем подключения
        sqlite_engine = create_engine(sqlite_url, echo=False)
        postgres_engine = create_engine(postgres_url, echo=False)

        SqliteSession = sessionmaker(bind=sqlite_engine)
        PostgresSession = sessionmaker(bind=postgres_engine)

        # Проверяем что SQLite БД существует
        if not os.path.exists(sqlite_path):
            logger.error(f"❌ SQLite файл не найден: {sqlite_path}")
            return False

        logger.info("\n✅ Подключения установлены")

        # Создаем таблицы в PostgreSQL (если не существуют)
        Base.metadata.create_all(postgres_engine)
        logger.info("✅ Таблицы PostgreSQL созданы/проверены")

        # Открываем сессии
        sqlite_session = SqliteSession()
        postgres_session = PostgresSession()

        try:
            # Список таблиц для миграции
            models = [
                (User, "users"),
                (Training, "trainings"),
                (Goal, "goals"),
                (TrainingPlan, "training_plan"),
                (WellnessSurvey, "wellness_surveys")
            ]

            total_migrated = 0

            for model, name in models:
                logger.info(f"\n📋 Миграция {name}...")

                # Получаем данные из SQLite
                sqlite_records = sqlite_session.query(model).all()
                count = len(sqlite_records)

                if count == 0:
                    logger.info(f"  ⏭️  Нет данных для миграции")
                    continue

                logger.info(f"  📊 Найдено записей: {count}")

                # Проверяем существующие записи в PostgreSQL
                postgres_count = postgres_session.query(model).count()

                if postgres_count > 0:
                    logger.info(f"  ⚠️  PostgreSQL уже содержит {postgres_count} записей")
                    logger.info(f"  🔄 Добавляем только новые записи...")

                # Копируем записи
                migrated = 0
                for record in sqlite_records:
                    # Создаем копию объекта без id (чтобы PostgreSQL сгенерировал новый)
                    record_dict = {
                        c.name: getattr(record, c.name)
                        for c in record.__table__.columns
                        if c.name != 'id'  # Исключаем primary key
                    }

                    # Проверяем есть ли уже такая запись
                    # (по уникальным полям, если есть)
                    exists = False
                    if hasattr(model, 'telegram_id') and 'telegram_id' in record_dict:
                        exists = postgres_session.query(model).filter_by(
                            telegram_id=record_dict['telegram_id']
                        ).first() is not None

                    if not exists:
                        new_record = model(**record_dict)
                        postgres_session.add(new_record)
                        migrated += 1

                # Коммитим изменения
                postgres_session.commit()
                logger.info(f"  ✅ Мигрировано новых записей: {migrated}/{count}")
                total_migrated += migrated

            logger.info("\n" + "=" * 60)
            logger.info(f"✅ МИГРАЦИЯ ЗАВЕРШЕНА")
            logger.info(f"📊 Всего перенесено записей: {total_migrated}")
            logger.info("=" * 60)

            # Проверка итоговых данных
            logger.info("\n📊 Итоговые данные в PostgreSQL:")
            for model, name in models:
                count = postgres_session.query(model).count()
                logger.info(f"  {name}: {count} записей")

            return True

        finally:
            sqlite_session.close()
            postgres_session.close()

    except Exception as e:
        logger.error(f"❌ Ошибка миграции: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = migrate_data()
    sys.exit(0 if success else 1)
