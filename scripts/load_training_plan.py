"""Загрузка плана тренировок в БД"""
import sys
import os
from pathlib import Path

# Устанавливаем минимальные переменные окружения для запуска
os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'dummy')
os.environ.setdefault('GARMIN_EMAIL', 'dummy')
os.environ.setdefault('GARMIN_PASSWORD', 'dummy')

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.training_plan_parser import parse_training_plan
from src.database.db import db
from src.database.init_db import init_database
from src.utils.logger import logger


def main():
    """Загрузка плана тренировок"""
    logger.info("=" * 50)
    logger.info("📅 Загрузка плана тренировок в БД")
    logger.info("=" * 50)

    # Инициализация БД
    if not init_database():
        logger.error("Не удалось инициализировать БД")
        return

    # Путь к файлу плана
    plan_file = Path(__file__).parent.parent.parent.parent / "План_адаптированный_март_апрель.md"

    if not plan_file.exists():
        logger.error(f"Файл плана не найден: {plan_file}")
        return

    logger.info(f"Читаю план из: {plan_file}")

    # Парсинг плана
    trainings = parse_training_plan(str(plan_file))

    if not trainings:
        logger.error("Не удалось распарсить план")
        return

    logger.info(f"Распарсено {len(trainings)} тренировок")

    # Создание тестового пользователя
    test_telegram_id = 123456789
    user = db.get_or_create_user(test_telegram_id)
    logger.info(f"Пользователь: ID={user.id}, Telegram={test_telegram_id}")

    # Загрузка плана в БД
    count = db.load_training_plan(user.id, trainings)

    logger.info("=" * 50)
    logger.info(f"✅ Загружено {count} тренировок")
    logger.info("=" * 50)

    # Показать несколько примеров
    logger.info("\n📋 Примеры загруженных тренировок:")
    for i, training in enumerate(trainings[:3], 1):
        logger.info(f"\n{i}. {training['date'].strftime('%d.%m.%Y')} ({training['date'].strftime('%A')})")
        logger.info(f"   Тип: {training['workout_type']}")
        logger.info(f"   Название: {training['workout_name']}")
        logger.info(f"   Длительность: {training.get('duration_min', '—')} мин")
        logger.info(f"   Расстояние: {training.get('distance_km', '—')} км")
        logger.info(f"   Зоны: {training.get('target_zone', '—')}")


if __name__ == "__main__":
    main()
