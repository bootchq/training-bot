"""Тестирование логики адаптации плана"""
import sys
import os
from pathlib import Path
from datetime import date, timedelta

# Устанавливаем минимальные переменные окружения
os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'dummy')
os.environ.setdefault('GARMIN_EMAIL', 'dummy')
os.environ.setdefault('GARMIN_PASSWORD', 'dummy')

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.db import db
from src.core.plan_adapter import PlanAdapter
from src.utils.logger import logger


def test_skip_adaptation():
    """Тест адаптации при пропуске тренировки"""
    logger.info("=" * 50)
    logger.info("🧪 Тест адаптации при пропуске")
    logger.info("=" * 50)

    # Получаем тестового пользователя
    test_telegram_id = 123456789
    user = db.get_or_create_user(test_telegram_id)

    # Создаём адаптер
    adapter = PlanAdapter(user.id)

    # Тестируем пропуск 29.12.2025 (первая тренировка в плане)
    skip_date = date(2025, 12, 29)

    logger.info(f"\nСимуляция пропуска тренировки: {skip_date}")

    # Анализ дня (нет факта)
    analysis = adapter.analyze_day(skip_date)

    logger.info(f"Статус: {analysis['status']}")
    logger.info(f"Сообщение: {analysis['message']}")

    # Адаптация
    if analysis['status'] == 'skipped':
        changes = adapter.adapt_on_skip(skip_date)

        if changes:
            logger.info(f"\n✅ Изменения внесены:")
            for change in changes:
                logger.info(f"  - {change}")
        else:
            logger.info("\nℹ️  Изменений не требуется")

    logger.info("\n" + "=" * 50)


def test_overperformance():
    """Тест адаптации при перевыполнении"""
    logger.info("\n" + "=" * 50)
    logger.info("🧪 Тест адаптации при перевыполнении")
    logger.info("=" * 50)

    test_telegram_id = 123456789
    user = db.get_or_create_user(test_telegram_id)

    # Добавляем фейковую тренировку с перевыполнением
    from src.database.db import Training

    test_date = date(2025, 12, 29)

    with db.get_session() as session:
        # Удаляем старые тесты
        session.query(Training).filter_by(user_id=user.id, date=test_date).delete()

        # Создаём тренировку с перевыполнением (план 10км → факт 20км)
        training = Training(
            user_id=user.id,
            date=test_date,
            type='actual',
            distance_km=20.0,  # План был ~10км
            duration_min=120,
            avg_hr=155
        )
        session.add(training)

    logger.info(f"Создана тренировка: 20км вместо ~10км")

    # Анализ
    adapter = PlanAdapter(user.id)
    analysis = adapter.analyze_day(test_date)

    logger.info(f"\nСтатус: {analysis['status']}")
    logger.info(f"Сообщение: {analysis['message']}")

    # Адаптация
    if analysis['status'] == 'overperformed':
        changes = adapter.adapt_on_overperformance(test_date)

        if changes:
            logger.info(f"\n✅ Изменения внесены:")
            for change in changes:
                logger.info(f"  - {change}")
        else:
            logger.info("\nℹ️  Изменений не требуется")

    logger.info("\n" + "=" * 50)


def test_wellness_adaptation():
    """Тест адаптации по самочувствию"""
    logger.info("\n" + "=" * 50)
    logger.info("🧪 Тест адаптации по самочувствию")
    logger.info("=" * 50)

    test_telegram_id = 123456789
    user = db.get_or_create_user(test_telegram_id)

    adapter = PlanAdapter(user.id)

    test_date = date(2025, 12, 28)  # День перед первой тренировкой

    # Тест 1: Плохое самочувствие (rating=3)
    logger.info(f"\nСимуляция опроса: самочувствие 3/10")
    changes = adapter.adapt_on_wellness(test_date, rating=3)

    if changes:
        logger.info(f"✅ Изменения:")
        for change in changes:
            logger.info(f"  - {change}")

    # Тест 2: Отличное самочувствие (rating=9)
    logger.info(f"\nСимуляция опроса: самочувствие 9/10")
    changes = adapter.adapt_on_wellness(test_date, rating=9)

    if changes:
        logger.info(f"✅ Изменения:")
        for change in changes:
            logger.info(f"  - {change}")

    logger.info("\n" + "=" * 50)


if __name__ == "__main__":
    # Тест 1: Пропуск
    test_skip_adaptation()

    # Тест 2: Перевыполнение
    # test_overperformance()

    # Тест 3: Самочувствие
    # test_wellness_adaptation()
