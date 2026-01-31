"""Планировщик задач"""
from datetime import timedelta, time as dt_time
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
from ..utils import time_utils


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

        # Задача в 09:00 - утреннее напоминание о тренировке
        self.scheduler.add_job(
            self.morning_reminder,
            trigger=CronTrigger(hour=9, minute=0),
            id='morning_reminder',
            name='Утреннее напоминание о тренировке',
            replace_existing=True
        )

        # Задача в 12:00 - удаление утреннего напоминания
        self.scheduler.add_job(
            self.delete_morning_reminders,
            trigger=CronTrigger(hour=12, minute=0),
            id='delete_morning',
            name='Удаление утренних напоминаний',
            replace_existing=True
        )

        # Задача в 21:00 - напоминание о синхронизации Garmin
        self.scheduler.add_job(
            self.sync_reminder,
            trigger=CronTrigger(hour=21, minute=0),
            id='sync_reminder',
            name='Напоминание о синхронизации Garmin',
            replace_existing=True
        )

        # Задача в воскресенье 20:00 - AI-анализ недели
        self.scheduler.add_job(
            self.weekly_ai_review,
            trigger=CronTrigger(day_of_week='sun', hour=20, minute=0),
            id='weekly_review',
            name='Еженедельный AI-анализ',
            replace_existing=True
        )

        self.scheduler.start()

        # Планируем напоминания за 2 часа до тренировок на следующие 7 дней
        self.schedule_pre_workout_reminders()

        logger.info("Планировщик запущен (00:00 - анализ, 01:00 - план, 09:00 - напоминание, 12:00 - удаление, 21:00 - синхронизация, вс 20:00 - итоги)")

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

            yesterday = time_utils.today() - timedelta(days=1)

            # 1. Синхронизация с Garmin за вчера
            logger.info(f"Синхронизация Garmin за {yesterday}...")
            count = garmin_sync.sync_date_for_user(self.user_id, yesterday)
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

            # 5. Перепланирование напоминаний за 2 часа на новый день
            self.schedule_pre_workout_reminders()

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
            today = time_utils.today()
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


    async def morning_reminder(self):
        """Утреннее напоминание о тренировке (09:00)"""
        try:
            if not self.telegram_bot:
                return

            today = time_utils.today()

            # Получаем план на сегодня
            plans = db.get_plan_for_week(self.user_id, today)
            today_plan = None
            for plan in plans:
                if plan.date == today:
                    today_plan = plan
                    break

            if not today_plan:
                logger.info(f"Напоминание: сегодня ({today}) нет тренировки")
                return

            # Получаем время тренировки из настроек пользователя
            user = db.get_user_by_id(self.user_id)
            workout_time = None
            if user:
                is_weekend = today.weekday() >= 5  # Суббота=5, Воскресенье=6
                workout_time = user.start_time_weekend if is_weekend else user.start_time_weekday

            # Форматируем напоминание
            emoji_map = {
                'длинная': '🏃‍♂️',
                'интервалы': '⚡',
                'темповый': '🔥',
                'восстановительная': '🧘',
                'кросс': '🌲',
                'легкая': '😊'
            }

            workout_type = today_plan.type.lower()
            emoji = '🏃'
            for key, e in emoji_map.items():
                if key in workout_type:
                    emoji = e
                    break

            text = f"{emoji} **Сегодня тренировка"
            if workout_time:
                text += f" в {workout_time}"
            text += "!**\n\n"
            text += f"**{today_plan.type.upper()}**\n"

            if today_plan.duration_min:
                text += f"⏱ {today_plan.duration_min} мин"
            if today_plan.distance_km:
                text += f" / ~{today_plan.distance_km:.1f} км"
            if today_plan.target_zone:
                text += f"\n🎯 Зоны: {today_plan.target_zone}"

            if today_plan.description:
                text += f"\n\n{today_plan.description}"

            text += "\n\n💪 Удачной тренировки!"

            # Отправляем сообщение и сохраняем message_id
            message = await self.telegram_bot.send_message(
                chat_id=self.telegram_id,
                text=text,
                parse_mode='Markdown'
            )

            # Сохраняем message_id для последующего удаления
            db.save_reminder(self.user_id, today, 'morning', message.message_id)

            logger.info(f"Утреннее напоминание отправлено: {today_plan.type}, message_id={message.message_id}")

        except Exception as e:
            logger.error(f"Ошибка утреннего напоминания: {e}", exc_info=True)

    async def weekly_ai_review(self):
        """Еженедельный AI-анализ (воскресенье 20:00)"""
        try:
            if not self.telegram_bot:
                return

            from ..integrations.ai_agent import ai_consultant

            logger.info("📊 Начало еженедельного AI-анализа")

            # Получаем статистику за неделю
            from ..core.stats_calculator import StatsCalculator
            calculator = StatsCalculator(self.user_id)
            week_stats = calculator.get_week_stats()

            if not week_stats.get('trainings'):
                await self.telegram_bot.send_message(
                    chat_id=self.telegram_id,
                    text="📊 **Итоги недели**\n\nНа этой неделе тренировок не было. Начни следующую неделю активно! 💪"
                )
                return

            # Получаем план на эту неделю для сравнения
            today = time_utils.today()
            start_of_week = today - timedelta(days=today.weekday())
            planned = db.get_plan_for_week(self.user_id, start_of_week)

            # Формируем контекст для AI
            context = f"""Проанализируй тренировочную неделю бегуна:

ПЛАН НА НЕДЕЛЮ:
{len(planned)} тренировок запланировано

ФАКТ:
- Тренировок выполнено: {week_stats.get('total_trainings', 0)}
- Общий объём: {week_stats.get('total_distance', 0):.1f} км
- Общее время: {week_stats.get('total_time', 0)} мин
- Средний темп: {week_stats.get('avg_pace', 'н/д')}
- Средний пульс: {week_stats.get('avg_hr', 'н/д')} уд/мин

ТРЕНИРОВКИ:
"""
            for t in week_stats.get('trainings', [])[:5]:
                context += f"- {t.get('date')}: {t.get('distance', 0):.1f} км, {t.get('duration', 0)} мин, пульс {t.get('avg_hr', 'н/д')}\n"

            context += """
Дай краткий анализ (3-4 предложения):
1. Выполнен ли план?
2. Что хорошо?
3. Над чем работать?
4. Рекомендация на следующую неделю
"""

            # Получаем AI-анализ
            ai_response = await ai_consultant.get_advice(
                user_id=self.user_id,
                context=context,
                training_data=week_stats
            )

            # Форматируем сообщение
            text = f"📊 **Итоги недели** ({start_of_week.strftime('%d.%m')} - {today.strftime('%d.%m')})\n\n"
            text += f"🏃 Тренировок: {week_stats.get('total_trainings', 0)}\n"
            text += f"📏 Объём: {week_stats.get('total_distance', 0):.1f} км\n"
            text += f"⏱ Время: {week_stats.get('total_time', 0)} мин\n\n"
            text += f"**🤖 AI-анализ:**\n{ai_response}"

            await self.telegram_bot.send_message(
                chat_id=self.telegram_id,
                text=text,
                parse_mode='Markdown'
            )

            logger.info("Еженедельный AI-анализ отправлен")

        except Exception as e:
            logger.error(f"Ошибка еженедельного анализа: {e}", exc_info=True)

    async def delete_morning_reminders(self):
        """Удаление утренних напоминаний (12:00)"""
        try:
            if not self.telegram_bot:
                return

            today = time_utils.today()

            # Получаем все утренние напоминания за сегодня
            reminders = db.get_reminders_to_delete(self.user_id, today, 'morning')

            if not reminders:
                logger.info(f"Нет утренних напоминаний для удаления за {today}")
                return

            deleted_count = 0
            for reminder in reminders:
                try:
                    await self.telegram_bot.delete_message(
                        chat_id=self.telegram_id,
                        message_id=reminder.message_id
                    )
                    db.mark_reminder_deleted(reminder.id)
                    deleted_count += 1
                    logger.info(f"Удалено утреннее напоминание message_id={reminder.message_id}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить сообщение {reminder.message_id}: {e}")

            logger.info(f"Удалено {deleted_count} утренних напоминаний")

        except Exception as e:
            logger.error(f"Ошибка удаления утренних напоминаний: {e}", exc_info=True)

    async def sync_reminder(self):
        """Напоминание о синхронизации Garmin (21:00)"""
        try:
            if not self.telegram_bot:
                return

            today = time_utils.today()

            # Проверяем был ли план на сегодня
            plans = db.get_plan_for_week(self.user_id, today)
            today_plan = None
            for plan in plans:
                if plan.date == today:
                    today_plan = plan
                    break

            if not today_plan:
                logger.info(f"Напоминание о синхронизации: сегодня ({today}) не было тренировки")
                return

            # Проверяем есть ли данные в Garmin за сегодня
            training = db.get_training_for_date(self.user_id, today)

            if training and training.type == 'actual':
                logger.info(f"Тренировка за {today} уже синхронизирована, напоминание не нужно")
                return

            # Отправляем напоминание
            text = (
                "📲 **Напоминание о синхронизации**\n\n"
                "Сегодня была запланирована тренировка, но данных в Garmin нет.\n\n"
                "Не забудь синхронизировать часы с телефоном!"
            )

            message = await self.telegram_bot.send_message(
                chat_id=self.telegram_id,
                text=text,
                parse_mode='Markdown'
            )

            # Сохраняем message_id
            db.save_reminder(self.user_id, today, 'sync', message.message_id)

            logger.info(f"Напоминание о синхронизации отправлено, message_id={message.message_id}")

        except Exception as e:
            logger.error(f"Ошибка напоминания о синхронизации: {e}", exc_info=True)

    def schedule_pre_workout_reminders(self):
        """
        Планирование напоминаний за 2 часа до тренировок на следующие 7 дней
        """
        try:
            if not self.telegram_bot or not self.user_id:
                return

            today = time_utils.today()
            user = db.get_user_by_id(self.user_id)
            if not user:
                return

            # Получаем тренировки на следующие 7 дней
            end_date = today + timedelta(days=7)
            plans = db.get_plan_for_period(self.user_id, today, end_date)

            if not plans:
                logger.info("Нет тренировок на следующие 7 дней для планирования напоминаний")
                return

            scheduled_count = 0
            for plan in plans:
                # Определяем время тренировки
                is_weekend = plan.date.weekday() >= 5
                workout_time_str = user.start_time_weekend if is_weekend else user.start_time_weekday

                if not workout_time_str:
                    continue

                try:
                    # Парсим время тренировки
                    hour, minute = map(int, workout_time_str.split(':'))

                    # Время за 2 часа до тренировки
                    reminder_datetime = time_utils.combine_datetime(plan.date, dt_time(hour, minute))
                    reminder_datetime = reminder_datetime - timedelta(hours=2)

                    # Проверяем что напоминание в будущем
                    now = time_utils.now()
                    if reminder_datetime <= now:
                        continue

                    # Планируем напоминание за 2 часа
                    job_id_pre = f'pre_workout_{self.user_id}_{plan.date.isoformat()}'
                    self.scheduler.add_job(
                        self.send_pre_workout_reminder,
                        trigger='date',
                        run_date=reminder_datetime,
                        args=[plan.date, workout_time_str],
                        id=job_id_pre,
                        replace_existing=True
                    )

                    # Планируем удаление в время тренировки
                    workout_datetime = time_utils.combine_datetime(plan.date, dt_time(hour, minute))
                    job_id_delete = f'delete_workout_{self.user_id}_{plan.date.isoformat()}'
                    self.scheduler.add_job(
                        self.delete_workout_reminders,
                        trigger='date',
                        run_date=workout_datetime,
                        args=[plan.date],
                        id=job_id_delete,
                        replace_existing=True
                    )

                    scheduled_count += 1

                except Exception as e:
                    logger.warning(f"Ошибка планирования напоминания для {plan.date}: {e}")

            logger.info(f"Запланировано {scheduled_count} напоминаний за 2 часа до тренировок")

        except Exception as e:
            logger.error(f"Ошибка планирования напоминаний: {e}", exc_info=True)

    async def send_pre_workout_reminder(self, workout_date, workout_time: str):
        """
        Напоминание за 2 часа до тренировки

        Args:
            workout_date: Дата тренировки
            workout_time: Время тренировки (строка "HH:MM")
        """
        try:
            if not self.telegram_bot:
                return

            # Получаем план на эту дату
            plans = db.get_plan_for_week(self.user_id, workout_date)
            workout_plan = None
            for plan in plans:
                if plan.date == workout_date:
                    workout_plan = plan
                    break

            if not workout_plan:
                return

            # Форматируем сообщение
            text = f"⏰ **Через 2 часа тренировка!**\n\n"
            text += f"**{workout_plan.type.upper()}** в {workout_time}\n"

            if workout_plan.duration_min:
                text += f"⏱ {workout_plan.duration_min} мин"
            if workout_plan.distance_km:
                text += f" / ~{workout_plan.distance_km:.1f} км"

            text += "\n\n🏃 Готовься к выходу!"

            # Отправляем сообщение и сохраняем message_id
            message = await self.telegram_bot.send_message(
                chat_id=self.telegram_id,
                text=text,
                parse_mode='Markdown'
            )

            # Сохраняем message_id для последующего удаления
            db.save_reminder(self.user_id, workout_date, 'pre_workout', message.message_id)

            logger.info(f"Напоминание за 2 часа отправлено для {workout_date}, message_id={message.message_id}")

        except Exception as e:
            logger.error(f"Ошибка отправки напоминания за 2 часа: {e}", exc_info=True)

    async def delete_workout_reminders(self, workout_date):
        """
        Удаление напоминаний в время тренировки

        Args:
            workout_date: Дата тренировки
        """
        try:
            if not self.telegram_bot:
                return

            # Получаем все напоминания за 2 часа для этой даты
            reminders = db.get_reminders_to_delete(self.user_id, workout_date, 'pre_workout')

            if not reminders:
                logger.info(f"Нет напоминаний за 2 часа для удаления ({workout_date})")
                return

            deleted_count = 0
            for reminder in reminders:
                try:
                    await self.telegram_bot.delete_message(
                        chat_id=self.telegram_id,
                        message_id=reminder.message_id
                    )
                    db.mark_reminder_deleted(reminder.id)
                    deleted_count += 1
                    logger.info(f"Удалено напоминание за 2 часа message_id={reminder.message_id}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить сообщение {reminder.message_id}: {e}")

            logger.info(f"Удалено {deleted_count} напоминаний в время тренировки")

        except Exception as e:
            logger.error(f"Ошибка удаления напоминаний в время тренировки: {e}", exc_info=True)


# Глобальный экземпляр
scheduler = TrainingScheduler()
