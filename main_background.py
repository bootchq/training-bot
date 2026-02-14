"""
Service 2: Фоновая логика и анализ (back_logica_raboty_i_analiz_trenirovok)

Асинхронные задачи:
- Проверка новых тренировок в Garmin (12:00, 00:30)
- Анализ план vs факт после каждой тренировки
- Проверка пропусков (00:50)
- Утренние напоминания (07:00)
- Еженедельный сводный анализ (Вс 20:00)

НЕ делает: обработку команд пользователя (это в Service 1)
"""
import asyncio
import os
import sys
from datetime import date
from datetime import timedelta
from pathlib import Path

# Добавляем корневую папку в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Telegram API для отправки сообщений
from telegram import Bot

from src.database.db import db
from src.database.init_db import init_database
from src.integrations.ai_agent import ai_consultant
from src.integrations.garmin_sync import garmin_sync
from src.utils.alerting import send_alert
from src.utils.config import Config
from src.utils.health_check import health_server
from src.utils.logger import logger

# Глобальный bot для отправки сообщений
telegram_bot = Bot(token=Config.TELEGRAM_BOT_TOKEN)


async def check_and_analyze_trainings():
    """
    Проверка новых тренировок в Garmin и анализ

    Запуск: 12:00 и 00:30
    """
    logger.info("🔍 Проверка новых тренировок в Garmin")

    users = db.get_all_onboarded_users()
    logger.info(f"Найдено {len(users)} пользователей с завершенным онбордингом")

    for user in users:
        try:
            # Получаем credentials пользователя из БД
            credentials = db.get_user_garmin_credentials(user.id)
            if not credentials:
                logger.debug(f"Нет Garmin credentials для user_id={user.id}")
                continue

            email, password = credentials

            # Авторизуемся в Garmin с credentials пользователя
            if not garmin_sync.login(email, password):
                logger.warning(f"Не удалось авторизоваться в Garmin для user_id={user.id}")
                continue

            # Синхронизируем тренировки за сегодня
            today = date.today()
            new_count = garmin_sync.sync_date(user.id, today)

            if new_count > 0:
                logger.info(f"✅ Найдено {new_count} новых тренировок для user_id={user.id}")

                # Получаем последнюю тренировку
                training = db.get_training_for_date(user.id, today)

                if training:
                    # Анализ план vs факт
                    await analyze_training(user.id, user.telegram_id, training)
            else:
                logger.debug(f"Новых тренировок для user_id={user.id} не найдено")

        except Exception as e:
            logger.error(f"❌ Ошибка проверки тренировок для user_id={user.id}: {e}", exc_info=True)
            send_alert("Garmin sync failed", error=e, context=f"user_id={user.id}")


async def analyze_training(user_id: int, telegram_id: int, training):
    """
    Анализ тренировки: план vs факт

    Args:
        user_id: ID пользователя в БД
        telegram_id: ID пользователя в Telegram
        training: Объект тренировки
    """
    try:
        logger.info(f"🔍 Анализ тренировки для user_id={user_id}")

        # Получаем план на сегодня
        today_plan = db.get_plan_for_date(user_id, training.date)

        # Формируем промпт для AI
        if today_plan:
            prompt = f"""Анализ тренировки (план vs факт):

ПЛАН:
- Тип: {today_plan.type}
- Дистанция: {today_plan.distance_km} км
- Длительность: {today_plan.duration_min} мин
- Зона: {today_plan.target_zone}

ФАКТ:
- Дистанция: {training.distance_km:.2f} км
- Время: {training.duration_min} мин
- Темп: {training.avg_pace}
- Средний пульс: {training.avg_hr} bpm
- Макс пульс: {training.max_hr} bpm

Дай краткий анализ (3-4 предложения):
1. Выполнен ли план?
2. Что хорошо?
3. Что улучшить?
"""
        else:
            prompt = f"""Анализ тренировки (без плана):

ФАКТ:
- Дистанция: {training.distance_km:.2f} км
- Время: {training.duration_min} мин
- Темп: {training.avg_pace}
- Средний пульс: {training.avg_hr} bpm
- Макс пульс: {training.max_hr} bpm

Дай краткий анализ тренировки (2-3 предложения)
"""

        # Получаем AI-анализ
        analysis = await ai_consultant.get_advice(
            user_id=user_id,
            context=prompt,
            training_data={'training': training}
        )

        # Формируем сообщение
        message = "🏃 **Тренировка завершена!**\n\n"

        if today_plan:
            message += f"📋 **План:** {today_plan.type}, {today_plan.distance_km} км\n"

        message += f"✅ **Факт:** {training.distance_km:.2f} км, {training.duration_min} мин\n"

        if training.avg_pace:
            message += f"⚡️ **Темп:** {training.avg_pace}\n"

        if training.avg_hr:
            message += f"💓 **Пульс:** {training.avg_hr} bpm\n"

        message += f"\n🤖 **Анализ:**\n{analysis}"

        # Отправляем пользователю
        await telegram_bot.send_message(
            chat_id=telegram_id,
            text=message,
            parse_mode='Markdown'
        )

        logger.info(f"✅ Анализ отправлен user_id={user_id}")

    except Exception as e:
        logger.error(f"❌ Ошибка анализа тренировки для user_id={user_id}: {e}", exc_info=True)
        send_alert("AI analysis failed", error=e, context=f"user_id={user_id}")


async def check_missed_trainings():
    """
    Проверка пропущенных тренировок

    Запуск: 00:50 (проверяем вчерашний день)
    """
    logger.info("🔍 Проверка пропущенных тренировок")

    users = db.get_all_onboarded_users()
    yesterday = date.today() - timedelta(days=1)

    logger.info(f"Проверка пропусков за {yesterday.strftime('%d.%m.%Y')}")

    for user in users:
        try:
            # Проверяем был ли план на вчера
            plan = db.get_plan_for_date(user.id, yesterday)

            if not plan:
                logger.debug(f"Нет плана на {yesterday} для user_id={user.id}")
                continue

            # Проверяем была ли тренировка
            training = db.get_training_for_date(user.id, yesterday)

            if not training:
                # ПРОПУСК!
                logger.info(f"⏭️ Пропуск тренировки user_id={user.id} на {yesterday}")

                # Анализ пропуска и адаптация плана
                await analyze_skip(user.id, user.telegram_id, plan, yesterday)

        except Exception as e:
            logger.error(f"❌ Ошибка проверки пропусков для user_id={user.id}: {e}", exc_info=True)


async def analyze_skip(user_id: int, telegram_id: int, plan, skip_date):
    """
    Анализ пропуска и адаптация плана

    Args:
        user_id: ID пользователя
        telegram_id: ID в Telegram
        plan: План тренировки который пропущен
        skip_date: Дата пропуска
    """
    try:
        logger.info(f"🔍 Анализ пропуска для user_id={user_id}")

        # Адаптируем план
        from src.core.plan_adapter import PlanAdapter
        adapter = PlanAdapter(user_id)
        changes = adapter.adapt_on_skip(skip_date)

        # Формируем сообщение
        message = "⏭️ **Пропуск тренировки**\n\n"
        message += f"📋 План на {skip_date.strftime('%d.%m')}: {plan.type}, {plan.distance_km} км\n"
        message += "❌ Тренировки не было\n\n"

        if changes:
            message += "🔄 **Адаптация плана:**\n"
            for change in changes:
                message += f"• {change}\n"
        else:
            message += "✅ План не меняется (1-2 пропуска не критичны)\n\n"
            message += "💡 Продолжай тренировки по плану"

        # Отправляем пользователю
        await telegram_bot.send_message(
            chat_id=telegram_id,
            text=message,
            parse_mode='Markdown'
        )

        logger.info(f"✅ Анализ пропуска отправлен user_id={user_id}")

    except Exception as e:
        logger.error(f"❌ Ошибка анализа пропуска для user_id={user_id}: {e}", exc_info=True)


async def morning_reminders():
    """
    Утренние напоминания о тренировке

    Запуск: 07:00
    """
    logger.info("☀️ Отправка утренних напоминаний")

    users = db.get_all_onboarded_users()
    today = date.today()

    for user in users:
        try:
            # Проверяем есть ли тренировка на сегодня
            plan = db.get_plan_for_date(user.id, today)

            if plan:
                message = "☀️ **Доброе утро!**\n\n"
                message += f"Сегодня: {plan.type}\n"
                message += f"📏 {plan.distance_km} км, ~{plan.duration_min} мин\n"
                message += f"🎯 Зона: {plan.target_zone}\n\n"

                if plan.description:
                    message += f"💪 {plan.description}"

                await telegram_bot.send_message(
                    chat_id=user.telegram_id,
                    text=message,
                    parse_mode='Markdown'
                )

                logger.info(f"✅ Утреннее напоминание отправлено user_id={user.id}")

        except Exception as e:
            logger.error(f"❌ Ошибка утреннего напоминания для user_id={user.id}: {e}", exc_info=True)


async def weekly_summary():
    """
    Еженедельный сводный анализ

    Запуск: Воскресенье 20:00
    """
    logger.info("📊 Еженедельный сводный анализ")

    users = db.get_all_onboarded_users()

    for user in users:
        try:
            from src.core.stats_calculator import StatsCalculator
            calculator = StatsCalculator(user.id)
            week_stats = calculator.get_week_stats()

            if not week_stats.get('trainings') or week_stats['trainings_count'] == 0:
                logger.debug(f"Нет тренировок за неделю для user_id={user.id}")
                continue

            # Формируем сообщение
            today = date.today()
            start_of_week = today - timedelta(days=today.weekday())

            message = "📊 **Итоги недели**\n"
            message += f"({start_of_week.strftime('%d.%m')} - {today.strftime('%d.%m')})\n\n"
            message += f"🏃 Тренировок: {week_stats['trainings_count']}\n"
            message += f"📏 Объём: {week_stats['total_distance']:.1f} км\n"
            message += f"⏱ Время: {week_stats['total_hours']}ч {week_stats['total_minutes']}мин\n\n"
            message += "💪 Отличная неделя! Продолжай в том же духе"

            await telegram_bot.send_message(
                chat_id=user.telegram_id,
                text=message,
                parse_mode='Markdown'
            )

            logger.info(f"✅ Еженедельный анализ отправлен user_id={user.id}")

        except Exception as e:
            logger.error(f"❌ Ошибка еженедельного анализа для user_id={user.id}: {e}", exc_info=True)


async def run_background_jobs():
    """Запуск фоновых задач"""
    logger.info("🔧 Запуск Service 2: Фоновая логика и анализ")

    # Запускаем health check сервер
    await health_server.start()

    # Создаём scheduler
    scheduler = AsyncIOScheduler()

    # Проверка новых тренировок: 12:00 и 00:30
    scheduler.add_job(
        check_and_analyze_trainings,
        CronTrigger(hour=12, minute=0, timezone='Europe/Moscow'),
        id='check_noon',
        name='Проверка Garmin 12:00'
    )
    scheduler.add_job(
        check_and_analyze_trainings,
        CronTrigger(hour=0, minute=30, timezone='Europe/Moscow'),
        id='check_night',
        name='Проверка Garmin 00:30'
    )

    # Анализ пропусков: 00:50
    scheduler.add_job(
        check_missed_trainings,
        CronTrigger(hour=0, minute=50, timezone='Europe/Moscow'),
        id='check_missed',
        name='Проверка пропусков 00:50'
    )

    # Утренние напоминания: 07:00
    scheduler.add_job(
        morning_reminders,
        CronTrigger(hour=7, minute=0, timezone='Europe/Moscow'),
        id='morning',
        name='Утренние напоминания 07:00'
    )

    # Еженедельный анализ: Воскресенье 20:00
    scheduler.add_job(
        weekly_summary,
        CronTrigger(day_of_week='sun', hour=20, minute=0, timezone='Europe/Moscow'),
        id='weekly',
        name='Еженедельный анализ Вс 20:00'
    )

    scheduler.start()
    logger.info("✅ Все задачи запланированы:")
    for job in scheduler.get_jobs():
        logger.info(f"  - {job.name} (ID: {job.id})")

    # Держим процесс запущенным
    await asyncio.Event().wait()


def main():
    """Основная функция"""
    logger.info("=" * 50)
    logger.info("🏃 Запуск Service 2: Фоновая логика")
    logger.info("=" * 50)

    # Инициализация БД
    if not init_database():
        logger.error("Не удалось инициализировать БД. Выход.")
        return

    # Получаем порт из переменной окружения (Railway)
    port = int(os.getenv('PORT', 8080))
    health_server.port = port

    # Запуск фоновых задач
    try:
        asyncio.run(run_background_jobs())
    except KeyboardInterrupt:
        logger.info("Остановка фоновых задач (Ctrl+C)")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        send_alert("Service 2 CRASHED", error=e)
    finally:
        # Останавливаем health check сервер
        try:
            asyncio.run(health_server.stop())
        except Exception as e:
            logger.error(f"Ошибка остановки health check: {e}")

        logger.info("=" * 50)
        logger.info("👋 Фоновые задачи остановлены")
        logger.info("=" * 50)


if __name__ == "__main__":
    main()
