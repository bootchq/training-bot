"""Планировщик задач"""
from datetime import date, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot

from ..database.db import db
from ..integrations.garmin_sync import garmin_sync
from ..integrations.calendar_sync import calendar_sync
from ..core.plan_adapter import PlanAdapter
from ..core.wellness_survey import WellnessSurvey
from ..utils.config import Config
from ..utils.logger import logger


class TrainingScheduler:
    """Планировщик задач бота"""

    def __init__(self, telegram_bot: Bot = None):
        """
        Инициализация планировщика

        Args:
            telegram_bot: Экземпляр Telegram бота для отправки сообщений
        """
        self.scheduler = AsyncIOScheduler(timezone='Europe/Moscow')
        self.telegram_bot = telegram_bot
        self.user_id = None  # Будет установлен при старте

    def start(self, user_id: int, telegram_id: int):
        """
        Запуск планировщика

        Args:
            user_id: ID пользователя в БД
            telegram_id: Telegram ID для отправки сообщений
        """
        self.user_id = user_id
        self.telegram_id = telegram_id

        # Задача в 00:00 - анализ и адаптация
        self.scheduler.add_job(
            self.daily_analysis,
            trigger=CronTrigger(hour=0, minute=0),
            id='daily_analysis',
            name='Ежедневный анализ и адаптация',
            replace_existing=True
        )

        # Задача в 01:00 - отправка плана
        self.scheduler.add_job(
            self.send_weekly_plan,
            trigger=CronTrigger(hour=1, minute=0),
            id='send_plan',
            name='Отправка плана на неделю',
            replace_existing=True
        )

        self.scheduler.start()
        logger.info("Планировщик запущен (00:00 - анализ, 01:00 - план)")

    def stop(self):
        """Остановка планировщика"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Планировщик остановлен")

    async def daily_analysis(self):
        """Ежедневный анализ и адаптация (00:00)"""
        try:
            logger.info("=" * 50)
            logger.info("🔄 Начало ежедневного анализа")
            logger.info("=" * 50)

            yesterday = date.today() - timedelta(days=1)

            # 1. Синхронизация с Garmin за вчера
            logger.info(f"Синхронизация Garmin за {yesterday}...")
            count = garmin_sync.sync_date(self.user_id, yesterday)
            logger.info(f"Синхронизировано {count} тренировок")

            # 2. Анализ выполнения плана
            adapter = PlanAdapter(self.user_id)
            analysis = adapter.analyze_day(yesterday)

            logger.info(f"Статус: {analysis['status']}")
            logger.info(f"Сообщение: {analysis['message']}")

            # 3. Адаптация плана
            changes = []

            if analysis['status'] == 'skipped':
                # Пропуск тренировки
                skip_changes = adapter.adapt_on_skip(yesterday)
                changes.extend(skip_changes)

            elif analysis['status'] == 'overperformed':
                # Перевыполнение
                overperf_changes = adapter.adapt_on_overperformance(yesterday)
                changes.extend(overperf_changes)

            elif analysis['status'] == 'high_hr':
                # Высокий пульс на лёгкой
                if self.telegram_bot:
                    await self.telegram_bot.send_message(
                        chat_id=self.telegram_id,
                        text=f"⚠️ {analysis['message']}\n\nСледующую лёгкую тренировку беги спокойнее!"
                    )

            # Логируем изменения
            if changes:
                logger.info(f"Внесены изменения в план:")
                for change in changes:
                    logger.info(f"  - {change}")

                # Отправляем уведомление
                if self.telegram_bot:
                    changes_text = "\n".join([f"• {c}" for c in changes])
                    await self.telegram_bot.send_message(
                        chat_id=self.telegram_id,
                        text=f"📋 План адаптирован:\n\n{changes_text}"
                    )
            else:
                logger.info("Изменений в плане нет")

            # 4. Отправка опроса самочувствия (если была тренировка)
            if WellnessSurvey.should_send_survey(self.user_id, yesterday):
                logger.info(f"Тренировка за {yesterday} найдена - отправляю опрос")

                if self.telegram_bot:
                    text, keyboard = WellnessSurvey.create_survey_message(self.user_id, yesterday)
                    await self.telegram_bot.send_message(
                        chat_id=self.telegram_id,
                        text=text,
                        reply_markup=keyboard
                    )
                    logger.info("Опрос отправлен")
                else:
                    logger.warning("Telegram бот не настроен, опрос не отправлен")
            else:
                logger.info(f"Тренировка за {yesterday} не найдена - опрос не требуется")

            logger.info("=" * 50)
            logger.info("✅ Ежедневный анализ завершён")
            logger.info("=" * 50)

        except Exception as e:
            logger.error(f"Ошибка в ежедневном анализе: {e}", exc_info=True)

    async def send_weekly_plan(self):
        """Отправка плана на неделю (01:00)"""
        try:
            logger.info("📅 Отправка плана на неделю")

            if not self.telegram_bot:
                logger.warning("Telegram бот не настроен, план не отправлен")
                return

            # Получаем план на текущую неделю
            today = date.today()
            start_of_week = today - timedelta(days=today.weekday())

            plans = db.get_plan_for_week(self.user_id, start_of_week)

            if not plans:
                logger.warning("План на неделю не найден")
                return

            # Форматируем план
            plan_text = f"📅 План тренировок на неделю ({start_of_week.strftime('%d.%m')} - {(start_of_week + timedelta(days=6)).strftime('%d.%m')})\n\n"

            days_ru = {
                0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"
            }

            for plan in plans:
                day_name = days_ru.get(plan.date.weekday(), "")
                plan_text += f"**{day_name} {plan.date.strftime('%d.%m')}** — {plan.type.upper()}\n"

                if plan.duration_min:
                    plan_text += f"   ⏱ {plan.duration_min} мин"

                if plan.distance_km:
                    plan_text += f" / {plan.distance_km:.1f} км"

                if plan.target_zone:
                    plan_text += f" / {plan.target_zone}"

                plan_text += "\n\n"

            # Отправляем текстовый план
            await self.telegram_bot.send_message(
                chat_id=self.telegram_id,
                text=plan_text,
                parse_mode='Markdown'
            )

            logger.info("План отправлен")

            # Отправляем ICS файл для импорта в iPhone Calendar
            try:
                ics_path = calendar_sync.generate_ics_file(self.user_id, start_of_week, weeks=1)

                if ics_path:
                    # Отправляем ICS файл документом
                    with open(ics_path, 'rb') as ics_file:
                        await self.telegram_bot.send_document(
                            chat_id=self.telegram_id,
                            document=ics_file,
                            filename=f'план_{start_of_week.strftime("%d.%m")}.ics',
                            caption=(
                                "📲 ICS файл для импорта в календарь iPhone:\n\n"
                                "1. Скачай файл\n"
                                "2. Открой его\n"
                                "3. Выбери \"Добавить в Календарь\"\n\n"
                                "План автоматически синхронизируется с iCloud и всеми устройствами"
                            )
                        )
                    logger.info("ICS файл отправлен")
            except Exception as e:
                logger.error(f"Ошибка отправки ICS файла: {e}")

        except Exception as e:
            logger.error(f"Ошибка отправки плана: {e}", exc_info=True)


# Глобальный экземпляр
scheduler = TrainingScheduler()
