"""Тест отображения плана тренировок"""
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
from src.utils.logger import logger


def test_plan_display():
    """Тест форматирования плана"""
    logger.info("=" * 50)
    logger.info("📅 Тест отображения плана на неделю")
    logger.info("=" * 50)

    # Получаем тестового пользователя
    test_telegram_id = 123456789
    user = db.get_or_create_user(test_telegram_id)

    # Определяем начало недели (29.12.2025 - понедельник)
    start_of_week = date(2025, 12, 29)

    # Получаем план на неделю
    plans = db.get_plan_for_week(user.id, start_of_week)

    logger.info(f"Найдено {len(plans)} тренировок на неделю")

    if not plans:
        logger.error("План не найден. Запустите scripts/load_training_plan.py")
        return

    # Форматирование плана (как в боте)
    plan_text = f"📅 План тренировок ({start_of_week.strftime('%d.%m')} - {(start_of_week + timedelta(days=6)).strftime('%d.%m')})\n\n"

    days_ru = {
        0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"
    }

    for plan in plans:
        day_name = days_ru.get(plan.date.weekday(), "")
        plan_text += f"{day_name} {plan.date.strftime('%d.%m')} — {plan.type.upper()}\n"

        if plan.duration_min:
            plan_text += f"   ⏱ {plan.duration_min} мин"

        if plan.distance_km:
            plan_text += f" / {plan.distance_km:.0f} км"

        if plan.target_zone:
            plan_text += f" / {plan.target_zone}"

        plan_text += "\n\n"

    # Выводим результат
    logger.info("\n" + "=" * 50)
    logger.info("Форматированный план:\n")
    print(plan_text)
    logger.info("=" * 50)


if __name__ == "__main__":
    test_plan_display()
