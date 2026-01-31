"""Тестирование статистики"""
import os
import sys
from datetime import date
from datetime import timedelta
from pathlib import Path

# Устанавливаем минимальные переменные окружения
os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'dummy')
os.environ.setdefault('GARMIN_EMAIL', 'dummy')
os.environ.setdefault('GARMIN_PASSWORD', 'dummy')

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.stats_calculator import StatsCalculator
from src.database.db import Training
from src.database.db import db
from src.utils.logger import logger


def create_test_trainings():
    """Создать тестовые тренировки"""
    logger.info("=" * 50)
    logger.info("📝 Создание тестовых тренировок")
    logger.info("=" * 50)

    # Получаем тестового пользователя
    test_telegram_id = 123456789
    user = db.get_or_create_user(test_telegram_id)

    today = date.today()

    # Тренировки за последнюю неделю
    test_trainings = [
        # 7 дней назад - длинная
        {
            'date': today - timedelta(days=7),
            'distance_km': 20.0,
            'duration_min': 120,
            'avg_hr': 155,
            'hr_zones': {'z1': 600, 'z2': 5400, 'z3': 600, 'z4': 0, 'z5': 0}
        },
        # 5 дней назад - темповая
        {
            'date': today - timedelta(days=5),
            'distance_km': 12.0,
            'duration_min': 75,
            'avg_hr': 165,
            'hr_zones': {'z1': 300, 'z2': 2700, 'z3': 1500, 'z4': 0, 'z5': 0}
        },
        # 3 дня назад - интервалы
        {
            'date': today - timedelta(days=3),
            'distance_km': 10.0,
            'duration_min': 60,
            'avg_hr': 172,
            'hr_zones': {'z1': 300, 'z2': 1800, 'z3': 900, 'z4': 600, 'z5': 0}
        },
        # 1 день назад - восстановительная
        {
            'date': today - timedelta(days=1),
            'distance_km': 8.0,
            'duration_min': 50,
            'avg_hr': 148,
            'hr_zones': {'z1': 600, 'z2': 2400, 'z3': 0, 'z4': 0, 'z5': 0}
        },
    ]

    with db.get_session() as session:
        # Удаляем старые тесты
        session.query(Training).filter_by(user_id=user.id, type='actual').delete()

        for training_data in test_trainings:
            training = Training(
                user_id=user.id,
                type='actual',
                **training_data
            )
            session.add(training)

    logger.info(f"✅ Создано {len(test_trainings)} тестовых тренировок")
    logger.info("")


def test_week_stats():
    """Тест статистики за неделю"""
    logger.info("=" * 50)
    logger.info("🧪 Тест статистики за неделю")
    logger.info("=" * 50)

    test_telegram_id = 123456789
    user = db.get_or_create_user(test_telegram_id)

    # Создаём калькулятор
    calculator = StatsCalculator(user.id)

    # Получаем статистику
    stats = calculator.get_week_stats()

    # Форматируем
    stats_text = calculator.format_stats(stats)

    logger.info("\nСтатистика за неделю:")
    logger.info("")
    print(stats_text)
    logger.info("")

    # Проверка расчётов
    logger.info("Проверка расчётов:")
    logger.info(f"  Тренировок: {stats['trainings_count']} (ожидается: 4)")
    logger.info(f"  Объём: {stats['total_distance']:.1f}км (ожидается: 50.0)")
    logger.info(f"  Время: {stats['total_duration']}мин (ожидается: 305)")
    logger.info(f"  Средний пульс: {int(stats['avg_hr']) if stats['avg_hr'] else 'нет'} bpm (ожидается: ~160)")

    logger.info("=" * 50)


def test_month_stats():
    """Тест статистики за месяц"""
    logger.info("\n" + "=" * 50)
    logger.info("🧪 Тест статистики за месяц")
    logger.info("=" * 50)

    test_telegram_id = 123456789
    user = db.get_or_create_user(test_telegram_id)

    calculator = StatsCalculator(user.id)
    stats = calculator.get_month_stats()

    stats_text = calculator.format_stats(stats)

    logger.info("\nСтатистика за месяц:")
    logger.info("")
    print(stats_text)
    logger.info("")
    logger.info("=" * 50)


if __name__ == "__main__":
    # Создаём тестовые тренировки
    create_test_trainings()

    # Тест статистики за неделю
    test_week_stats()

    # Тест статистики за месяц
    test_month_stats()
