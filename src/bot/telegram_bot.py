"""Telegram бот"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, MessageHandler, filters
)

from ..utils.config import Config
from ..utils.logger import logger
from ..database.db import db
from ..integrations.garmin_sync import garmin_sync
from ..integrations.calendar_sync import calendar_sync
from ..core.scheduler import scheduler
from ..core.stats_calculator import StatsCalculator
from ..core.wellness_survey import WellnessSurvey

# Состояния для ConversationHandler
GARMIN_EMAIL, GARMIN_PASSWORD = range(2)


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
        # ConversationHandler для регистрации Garmin
        garmin_registration_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.ask_garmin_email, pattern="^register_garmin$")],
            states={
                GARMIN_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_garmin_email)],
                GARMIN_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_garmin_password)]
            },
            fallbacks=[CommandHandler("cancel", self.cancel_registration)]
        )

        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("sync", self.sync))
        self.app.add_handler(CommandHandler("stats", self.stats))
        self.app.add_handler(CommandHandler("plan", self.plan))
        self.app.add_handler(CommandHandler("calendar", self.calendar))
        self.app.add_handler(garmin_registration_handler)
        self.app.add_handler(CallbackQueryHandler(self.handle_survey_callback, pattern="^survey_"))
        self.app.add_handler(CallbackQueryHandler(self.handle_no_garmin_account, pattern="^no_garmin_account$"))
        self.app.add_handler(CallbackQueryHandler(self.handle_plan_generation, pattern="^plan_"))
        logger.info("Обработчики команд настроены")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        # Проверяем есть ли учетные данные Garmin
        credentials = db.get_user_garmin_credentials(user.id)

        if not credentials:
            # Новый пользователь - запрашиваем регистрацию
            keyboard = [
                [InlineKeyboardButton("✅ Есть аккаунт Garmin", callback_data="register_garmin")],
                [InlineKeyboardButton("❌ Нет аккаунта - зарегистрироваться", callback_data="no_garmin_account")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            welcome_text = """
🏃 Привет! Я твой бот-тренер по бегу.

Помогу подготовиться к забегам и адаптировать тренировки под твой уровень.

Для работы мне нужен доступ к твоим тренировкам в Garmin Connect.

У тебя есть аккаунт Garmin?
"""
            await update.message.reply_text(welcome_text, reply_markup=reply_markup)
            logger.info(f"Новый пользователь {telegram_id}, запрос регистрации Garmin")
            return

        # Запускаем scheduler при первом старте
        if not self.scheduler_started:
            scheduler.telegram_bot = self.app.bot
            scheduler.start(user.id, telegram_id)
            self.scheduler_started = True
            logger.info(f"Scheduler запущен для пользователя {telegram_id}")

        welcome_text = """
🏃 С возвращением!

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
        from datetime import date, timedelta

        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        # Проверяем есть ли credentials
        credentials = db.get_user_garmin_credentials(user.id)
        if not credentials:
            await update.message.reply_text(
                "❌ Учетные данные Garmin не найдены.\n\n"
                "Используй /start для регистрации"
            )
            return

        await update.message.reply_text("📥 Синхронизирую тренировки за последние 14 дней...")

        try:
            # Синхронизируем последние 14 дней
            total_count = 0
            today = date.today()

            for i in range(14):
                sync_date = today - timedelta(days=i)
                count = garmin_sync.sync_date_for_user(user.id, sync_date)
                total_count += count

            if total_count > 0:
                await update.message.reply_text(f"✅ Загружено {total_count} тренировок за последние 14 дней")
            else:
                await update.message.reply_text("ℹ️ Новых тренировок за последние 14 дней не найдено")
        except Exception as e:
            logger.error(f"Ошибка синхронизации для {telegram_id}: {e}")
            await update.message.reply_text(
                "❌ Ошибка синхронизации с Garmin.\n\n"
                "Проверь правильность логина/пароля в настройках аккаунта Garmin"
            )

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
            # Предлагаем создать план автоматически
            keyboard = [
                [InlineKeyboardButton("📅 Тарки-Тау 50км (15 фев)", callback_data="plan_tarki")],
                [InlineKeyboardButton("🏃 Марафон 42км (15 мар)", callback_data="plan_marathon")],
                [InlineKeyboardButton("⛰ DWT 65км (15 апр)", callback_data="plan_dwt")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                "📅 План тренировок не найден.\n\n"
                "Выбери цель для автоматической генерации плана:",
                reply_markup=reply_markup
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

    async def ask_garmin_email(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало регистрации - запрос email Garmin"""
        query = update.callback_query
        await query.answer()

        await query.edit_message_text(
            "📧 Введи свой email от Garmin Connect:\n\n"
            "Например: myemail@gmail.com\n\n"
            "Отправь /cancel для отмены"
        )
        return GARMIN_EMAIL

    async def receive_garmin_email(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение email и запрос пароля"""
        email = update.message.text.strip()

        # Базовая проверка email
        if '@' not in email or '.' not in email:
            await update.message.reply_text(
                "❌ Неверный формат email. Попробуй ещё раз.\n\n"
                "Отправь /cancel для отмены"
            )
            return GARMIN_EMAIL

        # Сохраняем email в контексте
        context.user_data['garmin_email'] = email

        await update.message.reply_text(
            "🔐 Теперь введи пароль от Garmin Connect:\n\n"
            "⚠️ Пароль будет сохранён зашифрованным для автоматической синхронизации\n\n"
            "Отправь /cancel для отмены"
        )
        return GARMIN_PASSWORD

    async def receive_garmin_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение пароля и завершение регистрации"""
        password = update.message.text.strip()
        email = context.user_data.get('garmin_email')

        if not email:
            await update.message.reply_text("❌ Ошибка: email не найден. Начни заново с /start")
            return ConversationHandler.END

        telegram_id = update.effective_user.id

        # Сохраняем учетные данные
        success = db.save_garmin_credentials(telegram_id, email, password)

        if not success:
            await update.message.reply_text(
                "❌ Ошибка сохранения данных. Попробуй позже.\n\n"
                "Используй /start для повторной попытки"
            )
            return ConversationHandler.END

        # Удаляем сообщение с паролем для безопасности
        try:
            await update.message.delete()
        except:
            pass

        await update.message.reply_text(
            "✅ Регистрация завершена!\n\n"
            "Теперь я могу автоматически синхронизировать твои тренировки с Garmin.\n\n"
            "Синхронизирую последние тренировки..."
        )

        # Запускаем первую синхронизацию
        user = db.get_or_create_user(telegram_id)
        try:
            # Синхронизируем последние 7 дней
            from datetime import date, timedelta
            count = 0
            for i in range(7):
                sync_date = date.today() - timedelta(days=i)
                count += garmin_sync.sync_date_for_user(user.id, sync_date)

            if count > 0:
                await update.message.reply_text(f"✅ Загружено {count} тренировок за последнюю неделю")
            else:
                await update.message.reply_text("ℹ️ Тренировок за последнюю неделю не найдено")

        except Exception as e:
            logger.error(f"Ошибка первой синхронизации: {e}")
            await update.message.reply_text(
                "⚠️ Не удалось синхронизировать тренировки.\n\n"
                "Проверь правильность логина/пароля и попробуй /sync"
            )

        # Запускаем scheduler
        if not self.scheduler_started:
            scheduler.telegram_bot = self.app.bot
            scheduler.start(user.id, telegram_id)
            self.scheduler_started = True

        await update.message.reply_text(
            "🎉 Всё готово!\n\n"
            "Команды:\n"
            "/sync — Синхронизация с Garmin (вручную)\n"
            "/stats — Статистика за неделю/месяц\n"
            "/plan — План на неделю\n"
            "/help — Помощь"
        )

        logger.info(f"Пользователь {telegram_id} завершил регистрацию Garmin")
        return ConversationHandler.END

    async def cancel_registration(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена регистрации"""
        await update.message.reply_text(
            "❌ Регистрация отменена.\n\n"
            "Используй /start когда будешь готов"
        )
        return ConversationHandler.END

    async def handle_no_garmin_account(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка кнопки 'Нет аккаунта Garmin'"""
        query = update.callback_query
        await query.answer()

        await query.edit_message_text(
            "📱 Для использования бота нужен аккаунт Garmin Connect\n\n"
            "Зарегистрироваться можно здесь:\n"
            "https://connect.garmin.com/signup\n\n"
            "После регистрации возвращайся и нажми /start"
        )

        logger.info(f"Пользователь {update.effective_user.id} запросил регистрацию Garmin")

    async def handle_plan_generation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка генерации плана тренировок"""
        from datetime import date
        from ..core.plan_generator import PlanGenerator

        query = update.callback_query
        await query.answer()

        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        # Определяем цель по callback_data
        goal_mapping = {
            'plan_tarki': {'name': 'Тарки-Тау 50км', 'distance': 50, 'date': date(2026, 2, 15)},
            'plan_marathon': {'name': 'Марафон 42км', 'distance': 42, 'date': date(2026, 3, 15)},
            'plan_dwt': {'name': 'DWT 65км', 'distance': 65, 'date': date(2026, 4, 15)}
        }

        goal_data = goal_mapping.get(query.data)

        if not goal_data:
            await query.edit_message_text("❌ Неизвестная цель")
            return

        await query.edit_message_text(
            f"⏳ Генерирую план подготовки к {goal_data['name']}...\n\n"
            "Это займёт несколько секунд"
        )

        # Генерируем план
        generator = PlanGenerator(user.id)
        trainings = generator.generate_base_plan(
            goal_distance=goal_data['distance'],
            goal_date=goal_data['date'],
            weeks=4  # Генерируем на 4 недели
        )

        # Сохраняем в БД
        count = generator.save_plan_to_db(trainings)

        await query.edit_message_text(
            f"✅ План создан!\n\n"
            f"🎯 Цель: {goal_data['name']} ({goal_data['date'].strftime('%d.%m.%Y')})\n"
            f"📅 Сгенерировано тренировок: {count}\n"
            f"📆 Период: 4 недели\n\n"
            "Используй /plan чтобы посмотреть план на неделю"
        )

        logger.info(f"Пользователь {telegram_id} сгенерировал план для {goal_data['name']}")

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
