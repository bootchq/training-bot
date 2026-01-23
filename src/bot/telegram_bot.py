"""Telegram бот"""
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from ..utils.config import Config
from ..utils.logger import logger
from ..database.db import db
from ..integrations.garmin_sync import garmin_sync
from ..integrations.calendar_sync import calendar_sync
from ..core.scheduler import scheduler
from ..core.stats_calculator import StatsCalculator
from ..core.wellness_survey import WellnessSurvey


class TrainingBot:
    """Бот-тренер"""

    def __init__(self):
        """Инициализация бота"""
        self.token = Config.TELEGRAM_BOT_TOKEN
        self.app = Application.builder().token(self.token).build()
        self._setup_handlers()
        self.scheduler_started = False
        logger.info("Бот инициализирован")

    def _setup_handlers(self):
        """Настройка обработчиков команд"""
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("sync", self.sync))
        self.app.add_handler(CommandHandler("stats", self.stats))
        self.app.add_handler(CommandHandler("plan", self.plan))
        self.app.add_handler(CommandHandler("calendar", self.calendar))
        self.app.add_handler(CallbackQueryHandler(self.handle_survey_callback, pattern="^survey_"))
        logger.info("Обработчики команд настроены")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        # Запускаем scheduler при первом старте
        if not self.scheduler_started:
            scheduler.telegram_bot = self.app.bot
            scheduler.start(user.id, telegram_id)
            self.scheduler_started = True
            logger.info(f"Scheduler запущен для пользователя {telegram_id}")

        welcome_text = """
🏃 Привет! Я твой бот-тренер по бегу.

Помогу подготовиться к забегам:
• Тарки-Тау 50км (15-16 февраля)
• Марафон 42км (март)
• DWT 65км (апрель)

Что я умею:
✅ Синхронизация с Garmin (00:00 автоматически)
✅ Адаптивный план тренировок
✅ Опросы самочувствия после тренировок
✅ Google Calendar интеграция
✅ Статистика и прогресс

Команды:
/sync — Синхронизация с Garmin (вручную)
/stats — Статистика за неделю/месяц
/plan — План на неделю
/calendar — Синхронизация с Google Calendar
/help — Помощь

Автоматически:
• 00:00 - анализ выполнения + адаптация + опрос
• 01:00 - отправка плана на неделю

Удачных тренировок! 💪
"""
        await update.message.reply_text(welcome_text)
        logger.info(f"Пользователь {telegram_id} запустил бота")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help"""
        help_text = """
📋 Доступные команды:

/start — Начало работы
/sync — Синхронизация с Garmin (вручную)
/plan — План тренировок на текущую неделю
/stats — Статистика за неделю
/stats month — Статистика за месяц
/calendar — Синхронизация с Google Calendar

✅ Реализовано:
• Автоматическая синхронизация Garmin (00:00)
• Адаптивный план тренировок
• Вечерний опрос самочувствия
• Интеграция с Google Calendar

🤖 В разработке:
• AI-консультант с советами
"""
        await update.message.reply_text(help_text)

    async def sync(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /sync - ручная синхронизация с Garmin"""
        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        await update.message.reply_text("📥 Синхронизирую тренировки с Garmin...")

        try:
            count = garmin_sync.sync_today(user.id)
            if count > 0:
                await update.message.reply_text(f"✅ Сохранено {count} тренировок")
            else:
                await update.message.reply_text("ℹ️ Тренировок за сегодня нет")
        except Exception as e:
            logger.error(f"Ошибка синхронизации для {telegram_id}: {e}")
            await update.message.reply_text("❌ Ошибка синхронизации. Проверь настройки Garmin.")

    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /stats - статистика за неделю/месяц"""
        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        # Создаём калькулятор
        calculator = StatsCalculator(user.id)

        # Получаем аргумент (week или month)
        args = context.args
        period = args[0] if args else 'week'

        if period == 'month':
            stats = calculator.get_month_stats()
        else:
            stats = calculator.get_week_stats()

        # Форматируем и отправляем
        stats_text = calculator.format_stats(stats)
        await update.message.reply_text(stats_text)

        logger.info(f"Пользователь {telegram_id} запросил статистику за {period}")

    async def plan(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /plan - показ плана на неделю"""
        from datetime import date, timedelta

        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        # Определяем начало текущей недели (понедельник)
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())

        # Получаем план на неделю
        plans = db.get_plan_for_week(user.id, start_of_week)

        if not plans:
            await update.message.reply_text(
                "📅 План тренировок на эту неделю не найден.\n\n"
                "Загрузи план через скрипт: python scripts/load_training_plan.py"
            )
            return

        # Форматирование плана
        plan_text = f"📅 План тренировок ({start_of_week.strftime('%d.%m')} - {(start_of_week + timedelta(days=6)).strftime('%d.%m')})\n\n"

        days_ru = {
            0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"
        }

        for plan in plans:
            day_name = days_ru.get(plan.date.weekday(), "")
            plan_text += f"**{day_name} {plan.date.strftime('%d.%m')}** — {plan.type.upper()}\n"

            if plan.duration_min:
                plan_text += f"   ⏱ {plan.duration_min} мин"

            if plan.distance_km:
                plan_text += f" / {plan.distance_km:.0f} км"

            if plan.target_zone:
                plan_text += f" / {plan.target_zone}"

            plan_text += "\n"

            # Добавляем описание (первые 100 символов)
            if plan.description:
                desc_short = plan.description[:100].replace('\n', ' ')
                plan_text += f"   {desc_short}...\n"

            plan_text += "\n"

        await update.message.reply_text(plan_text, parse_mode='Markdown')
        logger.info(f"Пользователь {telegram_id} запросил план на неделю")

    async def calendar(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /calendar - синхронизация с Google Calendar"""
        from datetime import date, timedelta

        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        await update.message.reply_text("📅 Синхронизирую план с Google Calendar...")

        try:
            # Определяем начало текущей недели
            today = date.today()
            start_of_week = today - timedelta(days=today.weekday())

            # Синхронизируем план
            result = calendar_sync.sync_weekly_plan(user.id, start_of_week)

            if result['success']:
                msg = f"✅ Синхронизация завершена:\n\n"
                msg += f"• Создано событий: {result['created']}\n"

                if result['errors'] > 0:
                    msg += f"• Ошибок: {result['errors']}"

                await update.message.reply_text(msg)
            else:
                error_msg = result.get('error', 'Неизвестная ошибка')
                await update.message.reply_text(
                    f"❌ Ошибка синхронизации: {error_msg}\n\n"
                    "Проверь авторизацию в Google Calendar или создай credentials.json"
                )

        except Exception as e:
            logger.error(f"Ошибка синхронизации календаря для {telegram_id}: {e}")
            await update.message.reply_text(
                "❌ Ошибка синхронизации с Google Calendar.\n\n"
                "Убедись что:\n"
                "1. Файл credentials.json в папке data/\n"
                "2. Ты прошёл OAuth авторизацию"
            )

        logger.info(f"Пользователь {telegram_id} запросил синхронизацию календаря")

        # Дополнительно отправляем ICS файл для импорта в iPhone
        try:
            ics_path = calendar_sync.generate_ics_file(user.id, start_of_week, weeks=1)

            if ics_path:
                # Отправляем ICS файл документом
                with open(ics_path, 'rb') as ics_file:
                    await update.message.reply_document(
                        document=ics_file,
                        filename=f'план_{start_of_week.strftime("%d.%m")}.ics',
                        caption=(
                            "📲 ICS файл для импорта в iPhone Calendar:\n\n"
                            "1. Скачай файл\n"
                            "2. Открой его\n"
                            "3. Выбери \"Добавить в Календарь\"\n\n"
                            "План автоматически добавится в твой календарь"
                        )
                    )
                logger.info(f"ICS файл отправлен пользователю {telegram_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки ICS файла: {e}")

    async def handle_survey_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатия кнопок опроса самочувствия"""
        from datetime import date, timedelta

        query = update.callback_query
        await query.answer()

        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        # Обрабатываем callback через WellnessSurvey
        result = WellnessSurvey.handle_callback(user.id, query.data)

        if result:
            text, keyboard = result
            if keyboard:
                # Есть ещё вопросы - обновляем сообщение с новыми кнопками
                await query.edit_message_text(text, reply_markup=keyboard)
            else:
                # Опрос завершён - финальное сообщение
                await query.edit_message_text(text)

                # Отправляем AI совет после завершения опроса
                try:
                    yesterday = date.today() - timedelta(days=1)
                    ai_advice = WellnessSurvey.get_ai_advice_for_survey(user.id, yesterday)

                    if ai_advice:
                        await self.app.bot.send_message(
                            chat_id=telegram_id,
                            text=f"🤖 Совет от AI-тренера:\n\n{ai_advice}"
                        )
                        logger.info(f"AI совет отправлен пользователю {telegram_id}")
                except Exception as e:
                    logger.error(f"Ошибка отправки AI совета: {e}")

        else:
            # Некорректный callback или опрос не найден
            await query.edit_message_text("Опрос не найден или уже завершён")

        logger.info(f"Пользователь {telegram_id} ответил на опрос: {query.data}")

    def run(self):
        """Запуск бота"""
        try:
            logger.info("🚀 Бот запущен")
            self.app.run_polling(allowed_updates=Update.ALL_TYPES)
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Telegram API: {e}")
            raise

    def stop(self):
        """Остановка бота"""
        if self.scheduler_started:
            scheduler.stop()
        logger.info("⏹️  Бот остановлен")
