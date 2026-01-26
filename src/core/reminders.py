"""Умные напоминания о тренировках"""
from datetime import datetime, timedelta, time as dt_time
from typing import Optional, Callable
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from ..database.db import db, Training
from ..utils.logger import logger


class ReminderScheduler:
    """Планировщик напоминаний о тренировках"""

    def __init__(self, send_message_callback: Callable):
        """
        Инициализация

        Args:
            send_message_callback: Функция для отправки сообщений пользователю
                                   Сигнатура: async def send(user_id: int, message: str)
        """
        self.scheduler = BackgroundScheduler(timezone='Europe/Moscow')
        self.send_message = send_message_callback
        self.scheduler.start()
        logger.info("🔔 Планировщик напоминаний запущен")

    def schedule_user_reminders(self, user_id: int):
        """
        Настроить напоминания для пользователя на основе его настроек

        Args:
            user_id: ID пользователя
        """
        user_settings = db.get_user_settings(user_id)

        if not user_settings or not user_settings.get('training_days') or not user_settings.get('training_time'):
            logger.warning(f"Нет настроек для напоминаний user_id={user_id}")
            return

        # Удаляем старые напоминания пользователя
        self.remove_user_reminders(user_id)

        training_days = user_settings['training_days']  # ["day_1", "day_2", ...]
        training_time_str = user_settings['training_time']  # "19:00"

        # Парсим время
        try:
            training_time = datetime.strptime(training_time_str, "%H:%M").time()
        except ValueError:
            logger.error(f"Некорректное время: {training_time_str}")
            return

        # Создаем напоминание за 2 часа до тренировки для каждого дня
        for day_str in training_days:
            day_num = int(day_str.replace("day_", ""))  # day_1 -> 1

            # Время напоминания (за 2 часа)
            reminder_time = self._subtract_hours(training_time, 2)

            # CronTrigger: день недели (0=Monday), час, минута
            trigger = CronTrigger(
                day_of_week=day_num - 1,  # APScheduler использует 0=Monday
                hour=reminder_time.hour,
                minute=reminder_time.minute,
                timezone='Europe/Moscow'
            )

            job_id = f"reminder_{user_id}_day_{day_num}"

            self.scheduler.add_job(
                func=self._send_training_reminder,
                trigger=trigger,
                args=[user_id, training_time_str],
                id=job_id,
                replace_existing=True
            )

            logger.info(f"✅ Напоминание настроено: user={user_id}, день={day_num}, время={reminder_time}")

    def _subtract_hours(self, time_obj: dt_time, hours: int) -> dt_time:
        """Вычесть часы из времени"""
        dummy_date = datetime.combine(datetime.today(), time_obj)
        new_date = dummy_date - timedelta(hours=hours)
        return new_date.time()

    def _send_training_reminder(self, user_id: int, training_time: str):
        """Отправить напоминание о тренировке"""
        user = db.get_user_by_id(user_id)
        if not user:
            return

        telegram_id = user.telegram_id

        # Получаем план на сегодня
        today_plan = self._get_today_plan(user_id)

        if today_plan:
            message = (
                f"⏰ Напоминание о тренировке\n\n"
                f"📅 Сегодня в {training_time}\n"
                f"📏 {today_plan}\n\n"
                f"Удачной тренировки! 💪"
            )
        else:
            message = (
                f"⏰ Напоминание о тренировке\n\n"
                f"📅 Сегодня в {training_time}\n\n"
                f"Не забудь потренироваться! 🏃"
            )

        # Отправляем асинхронно
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.create_task(self.send_message(telegram_id, message))
        logger.info(f"🔔 Отправлено напоминание user={user_id}")

    def _get_today_plan(self, user_id: int) -> Optional[str]:
        """Получить план тренировки на сегодня"""
        # TODO: интеграция с планировщиком тренировок
        # Пока возвращаем None, потом доработаем
        return None

    def schedule_missed_training_check(self):
        """Настроить ежедневную проверку пропущенных тренировок"""
        # Проверка каждый день в 23:00
        trigger = CronTrigger(hour=23, minute=0, timezone='Europe/Moscow')

        self.scheduler.add_job(
            func=self._check_all_missed_trainings,
            trigger=trigger,
            id="missed_trainings_check",
            replace_existing=True
        )

        logger.info("✅ Настроена проверка пропущенных тренировок (23:00 ежедневно)")

    def _check_all_missed_trainings(self):
        """Проверить всех пользователей на пропущенные тренировки"""
        # Получаем всех пользователей с завершенным онбордингом
        users = db.get_all_onboarded_users()

        today = datetime.now().date()
        today_weekday = today.weekday() + 1  # 1=Monday

        for user in users:
            user_settings = db.get_user_settings(user.id)
            if not user_settings or not user_settings.get('training_days'):
                continue

            # Проверяем, был ли сегодня запланирован тренировочный день
            training_days = user_settings['training_days']
            if f"day_{today_weekday}" not in training_days:
                continue

            # Проверяем, есть ли тренировка на сегодня
            has_training = self._user_has_training_today(user.id, today)

            if not has_training:
                # Отправляем мотивационное сообщение
                self._send_missed_training_message(user.telegram_id)

    def _user_has_training_today(self, user_id: int, date) -> bool:
        """Проверить, есть ли тренировка у пользователя на дату"""
        with db.get_session() as session:
            training = session.query(Training).filter(
                Training.user_id == user_id,
                Training.date == date,
                Training.type == 'actual'
            ).first()
            return training is not None

    def _send_missed_training_message(self, telegram_id: int):
        """Отправить сообщение о пропущенной тренировке"""
        message = (
            "😔 Сегодня была запланирована тренировка, но её не было\n\n"
            "Бывает! Главное не сдаваться.\n"
            "Перенести на завтра? 💪"
        )

        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.create_task(self.send_message(telegram_id, message))
        logger.info(f"📩 Отправлено сообщение о пропуске тренировки telegram_id={telegram_id}")

    def remove_user_reminders(self, user_id: int):
        """Удалить все напоминания пользователя (публичный метод)"""
        jobs = self.scheduler.get_jobs()
        removed_count = 0
        for job in jobs:
            if job.id.startswith(f"reminder_{user_id}_"):
                self.scheduler.remove_job(job.id)
                logger.info(f"🗑 Удалено напоминание: {job.id}")
                removed_count += 1
        logger.info(f"Удалено {removed_count} напоминаний для user_id={user_id}")
        return removed_count

    def schedule_weekly_report(self):
        """Настроить еженедельную отправку отчетов"""
        # Отправка каждый понедельник в 09:00
        trigger = CronTrigger(day_of_week=0, hour=9, minute=0, timezone='Europe/Moscow')

        self.scheduler.add_job(
            func=self._send_weekly_reports,
            trigger=trigger,
            id="weekly_reports",
            replace_existing=True
        )

        logger.info("✅ Настроена отправка еженедельных отчетов (понедельник 09:00)")

    def _send_weekly_reports(self):
        """Отправить еженедельные отчеты всем пользователям"""
        from ..core.stats_calculator import StatsCalculator
        from ..integrations.ai_agent import AIConsultant

        users = db.get_all_onboarded_users()
        ai_consultant = AIConsultant()

        for user in users:
            try:
                # Получаем статистику за неделю
                calculator = StatsCalculator(user.id)
                stats = calculator.get_week_stats()

                if stats['trainings_count'] == 0:
                    # Нет тренировок - мотивационное сообщение
                    message = (
                        "📊 Еженедельный отчет\n\n"
                        "😔 За последнюю неделю не было тренировок\n\n"
                        "Начни новую неделю с пробежки! Даже 15 минут лучше, чем ничего. 💪"
                    )
                else:
                    # Генерируем AI-отчет с мотивацией
                    report_prompt = f"""Ты тренер по бегу. Напиши мотивационный еженедельный отчет (3-4 предложения).

Статистика за неделю:
- Тренировок: {stats['trainings_count']}
- Объём: {stats['total_distance']:.1f} км
- Время: {stats['total_hours']}ч {stats['total_minutes']}мин
"""
                    if stats['avg_hr']:
                        report_prompt += f"- Средний пульс: {int(stats['avg_hr'])} bpm\n"

                    report_prompt += """
Формат:
1. Похвали за достижения
2. Отметь прогресс или его отсутствие
3. Дай совет на следующую неделю

Пиши дружелюбно, мотивируй, будь позитивным."""

                    try:
                        ai_motivation = ai_consultant.ask(report_prompt)
                        message = f"📊 Еженедельный отчет\n\n{ai_motivation}"
                    except Exception as e:
                        logger.error(f"Ошибка генерации AI-отчета для user={user.id}: {e}")
                        # Fallback без AI
                        message = (
                            f"📊 Еженедельный отчет\n\n"
                            f"🏃 Тренировок: {stats['trainings_count']}\n"
                            f"📏 Объём: {stats['total_distance']:.1f} км\n"
                            f"⏱ Время: {stats['total_hours']}ч {stats['total_minutes']}мин\n\n"
                            f"Отличная работа! Продолжай в том же духе! 💪"
                        )

                # Отправляем отчет
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                loop.create_task(self.send_message(user.telegram_id, message))
                logger.info(f"📊 Отправлен еженедельный отчет user={user.id}")

            except Exception as e:
                logger.error(f"Ошибка отправки отчета для user={user.id}: {e}")

    def shutdown(self):
        """Остановить планировщик"""
        self.scheduler.shutdown()
        logger.info("🔴 Планировщик напоминаний остановлен")


# Глобальный экземпляр (будет инициализирован в telegram_bot.py)
reminder_scheduler: Optional[ReminderScheduler] = None


def init_reminder_scheduler(send_message_callback: Callable):
    """Инициализировать планировщик напоминаний"""
    global reminder_scheduler
    reminder_scheduler = ReminderScheduler(send_message_callback)
    reminder_scheduler.schedule_missed_training_check()
    reminder_scheduler.schedule_weekly_report()
    return reminder_scheduler


def get_reminder_scheduler() -> Optional[ReminderScheduler]:
    """Получить экземпляр планировщика"""
    return reminder_scheduler
