"""Alembic environment configuration"""
import os
import sys
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Добавляем корень проекта в path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.db import Base
from src.utils.config import Config

# Метаданные моделей для autogenerate
target_metadata = Base.metadata


def get_url():
    """Получить URL базы данных"""
    if Config.DATABASE_URL:
        url = Config.DATABASE_URL
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url
    return f"sqlite:///{Config.DATABASE_PATH}"


def run_migrations_offline():
    """Оффлайн миграции (генерация SQL)"""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Онлайн миграции (применение к БД)"""
    configuration = {"sqlalchemy.url": get_url()}
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
