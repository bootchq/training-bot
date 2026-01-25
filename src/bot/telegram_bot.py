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
from ..core.scheduler import TrainingScheduler
from ..core.stats_calculator import StatsCalculator
from ..core.wellness_survey import WellnessSurvey
from ..core.plan_adapter import PlanAdapter

# Состояния для ConversationHandler
GARMIN_EMAIL, GARMIN_PASSWORD = range(2)
PLAN_DAYS, PLAN_TIME = range(2, 4)


class TrainingBot:
    """Бот-тренер"""

    def __init__(self):
        """Инициализация бота"""
        self.token = Config.TELEGRAM_BOT_TOKEN
        self.app = Application.builder().token(self.token).build()
        self._setup_handlers()
        self.user_schedulers = {}  # Словарь {user_id: scheduler}
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

        # ConversationHandler для создания плана
        plan_creation_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.ask_plan_days, pattern="^plan_")],
            states={
                PLAN_DAYS: [CallbackQueryHandler(self.receive_plan_days, pattern="^days_")],
                PLAN_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_plan_time)]
            },
            fallbacks=[CommandHandler("cancel", self.cancel_plan_creation)]
        )

        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("sync", self.sync))
        self.app.add_handler(CommandHandler("stats", self.stats))
        self.app.add_handler(CommandHandler("plan", self.plan))
        self.app.add_handler(CommandHandler("calendar", self.calendar))
        self.app.add_handler(CommandHandler("skip", self.skip_training))
        self.app.add_handler(garmin_registration_handler)
        self.app.add_handler(plan_creation_handler)
        self.app.add_handler(CallbackQueryHandler(self.handle_survey_callback, pattern="^survey_"))
        self.app.add_handler(CallbackQueryHandler(self.handle_no_garmin_account, pattern="^no_garmin_account$"))
        self.app.add_handler(CallbackQueryHandler(self.handle_quick_actions, pattern="^quick_"))
        # Debug: catch-all handler для неперехваченных callbacks
        self.app.add_handler(CallbackQueryHandler(self.debug_callback_handler))
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

        # Запускаем scheduler для пользователя
        if user.id not in self.user_schedulers:
            user_scheduler = TrainingScheduler(telegram_bot=self.app.bot)
            user_scheduler.start(user.id, telegram_id)
            self.user_schedulers[user.id] = user_scheduler
            logger.info(f"Scheduler запущен для пользователя {telegram_id}")

        welcome_text = """
🏃 С возвращением!

Автоматически:
• 00:00 - анализ выполнения + адаптация + опрос
• 01:00 - отправка плана на неделю

Используй кнопки ниже для быстрого доступа или команды:
/sync /stats /plan /calendar /help
"""
        # Inline кнопки для быстрого доступа
        keyboard = [
            [
                InlineKeyboardButton("📊 Статистика", callback_data="quick_stats"),
                InlineKeyboardButton("📅 План", callback_data="quick_plan")
            ],
            [
                InlineKeyboardButton("🔄 Синхронизация", callback_data="quick_sync"),
                InlineKeyboardButton("📲 Календарь", callback_data="quick_calendar")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
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
/calendar — Скачать план в ICS для календаря
/skip — Пропустить тренировку (сегодня)
/skip 25.01 — Пропустить тренировку на дату

✅ Реализовано:
• Автоматическая синхронизация Garmin
• Адаптивный план тренировок
• Вечерний опрос самочувствия
• Экспорт плана в календарь
• Пропуск тренировок с адаптацией

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

        # Проверяем есть ли credentials
        credentials = db.get_user_garmin_credentials(user.id)
        if not credentials:
            await update.message.reply_text(
                "📊 Статистика недоступна\n\n"
                "❌ Учетные данные Garmin не найдены.\n\n"
                "Используй /start для регистрации, затем посмотри статистику.",
                parse_mode='Markdown'
            )
            return

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
        await update.message.reply_text(stats_text, parse_mode='Markdown')

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

        # Отправляем заголовок
        await update.message.reply_text(
            f"📅 **План тренировок на неделю**\n"
            f"({start_of_week.strftime('%d.%m')} - {(start_of_week + timedelta(days=6)).strftime('%d.%m')})\n\n"
            f"Всего тренировок: {len(plans)}",
            parse_mode='Markdown'
        )

        # Отправляем каждую тренировку отдельным сообщением
        days_ru = {
            0: "Понедельник", 1: "Вторник", 2: "Среда", 3: "Четверг",
            4: "Пятница", 5: "Суббота", 6: "Воскресенье"
        }

        for plan in plans:
            day_name = days_ru.get(plan.date.weekday(), "")

            # Формируем детальное сообщение для тренировки
            plan_text = f"**{day_name} {plan.date.strftime('%d.%m')}**\n\n"

            # Добавляем описание (если есть детальное)
            if plan.description:
                plan_text += f"{plan.description}\n"
            else:
                # Fallback для старых тренировок без детального описания
                plan_text += f"**{plan.type.capitalize()}**\n"
                if plan.duration_min:
                    plan_text += f"- Время: {plan.duration_min} мин\n"
                if plan.distance_km:
                    plan_text += f"- Расстояние: ~{plan.distance_km:.1f} км\n"
                if plan.target_zone:
                    plan_text += f"- Зоны: {plan.target_zone}\n"

            await update.message.reply_text(plan_text, parse_mode='Markdown')

        logger.info(f"Пользователь {telegram_id} запросил план на неделю")

    async def calendar(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /calendar - экспорт плана в ICS файл для импорта в календарь"""
        from datetime import date, timedelta

        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        # Определяем начало текущей недели
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())

        # Проверяем что план существует
        plans = db.get_plan_for_week(user.id, start_of_week)

        if not plans:
            await update.message.reply_text(
                "📅 План тренировок не найден.\n\n"
                "Создай план командой /plan, затем экспортируй в календарь.",
                parse_mode='Markdown'
            )
            return

        await update.message.reply_text("📅 Генерирую ICS файл для импорта в календарь...")

        try:
            # Генерируем ICS файл
            ics_path = calendar_sync.generate_ics_file(user.id, start_of_week, weeks=1)

            if ics_path:
                # Отправляем ICS файл документом
                with open(ics_path, 'rb') as ics_file:
                    await update.message.reply_document(
                        document=ics_file,
                        filename=f'план_{start_of_week.strftime("%d_%m")}.ics',
                        caption=(
                            "📲 **ICS файл для импорта в календарь**\n\n"
                            "**iPhone/iPad:**\n"
                            "1. Скачай файл\n"
                            "2. Открой его\n"
                            "3. Нажми \"Добавить всё\"\n\n"
                            "**Android:**\n"
                            "1. Скачай файл\n"
                            "2. Открой Google Calendar\n"
                            "3. Настройки → Импорт/Экспорт → Импортировать\n\n"
                            "**Компьютер:**\n"
                            "1. Скачай файл\n"
                            "2. Открой в Google Calendar / Outlook / Apple Calendar\n\n"
                            f"План на неделю ({start_of_week.strftime('%d.%m')} - "
                            f"{(start_of_week + timedelta(days=6)).strftime('%d.%m')})\n"
                            f"Тренировок: {len(plans)}"
                        ),
                        parse_mode='Markdown'
                    )
                logger.info(f"ICS файл отправлен пользователю {telegram_id}")
            else:
                await update.message.reply_text(
                    "❌ Ошибка создания ICS файла.\n\n"
                    "Попробуй позже или обратись к разработчику."
                )

        except Exception as e:
            logger.error(f"Ошибка отправки ICS файла для {telegram_id}: {e}")
            await update.message.reply_text(
                "❌ Ошибка экспорта плана.\n\n"
                "Попробуй позже или создай план заново командой /plan"
            )

    async def skip_training(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /skip - пропустить тренировку сегодня или указанную дату"""
        from datetime import date, datetime

        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        # Определяем дату пропуска
        args = context.args if context.args else []

        if args:
            # Пользователь указал дату: /skip 25.01 или /skip 25.01.2026
            try:
                date_str = args[0]
                if len(date_str.split('.')) == 2:
                    # Формат ДД.ММ - добавляем текущий год
                    skip_date = datetime.strptime(f"{date_str}.{date.today().year}", "%d.%m.%Y").date()
                else:
                    # Формат ДД.ММ.ГГГГ
                    skip_date = datetime.strptime(date_str, "%d.%m.%Y").date()
            except ValueError:
                await update.message.reply_text(
                    "❌ Неверный формат даты.\n\n"
                    "Используй: `/skip` (сегодня) или `/skip 25.01`",
                    parse_mode='Markdown'
                )
                return
        else:
            # Без аргументов - пропускаем сегодня
            skip_date = date.today()

        # Проверяем есть ли план на эту дату
        plan = db.get_plan_for_date(user.id, skip_date)

        if not plan:
            await update.message.reply_text(
                f"ℹ️ На {skip_date.strftime('%d.%m.%Y')} тренировка не запланирована."
            )
            return

        # Адаптируем план
        adapter = PlanAdapter(user.id)
        changes = adapter.adapt_on_skip(skip_date)

        # Формируем ответ
        day_name = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'][skip_date.weekday()]
        response = f"⏭️ **Пропуск тренировки: {day_name} {skip_date.strftime('%d.%m')}**\n\n"
        response += f"Тренировка: {plan.type}, {plan.duration_min} мин\n\n"

        if changes:
            response += "📊 **Адаптация плана:**\n"
            for change in changes:
                response += f"• {change}\n"
        else:
            response += (
                "✅ План не меняется (best practice).\n\n"
                "1-2 пропуска не критичны — продолжай тренировки по плану.\n"
                "При 3+ пропусках подряд план будет адаптирован."
            )

        await update.message.reply_text(response, parse_mode='Markdown')
        logger.info(f"Пользователь {telegram_id} пропустил тренировку {skip_date}")

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

        # Запускаем scheduler для пользователя
        if user.id not in self.user_schedulers:
            user_scheduler = TrainingScheduler(telegram_bot=self.app.bot)
            user_scheduler.start(user.id, telegram_id)
            self.user_schedulers[user.id] = user_scheduler

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

    async def handle_quick_actions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка quick action кнопок"""
        query = update.callback_query
        logger.info(f"🔘 QUICK ACTION: user={update.effective_user.id}, data='{query.data}'")
        await query.answer()

        # Создаём адаптированный Update с message вместо callback_query
        # Это позволяет переиспользовать существующие команды
        class FakeMessage:
            def __init__(self, query):
                self.chat = query.message.chat
                self.message_id = query.message.message_id
                self._query = query

            async def reply_text(self, *args, **kwargs):
                await self._query.message.reply_text(*args, **kwargs)

            async def reply_document(self, *args, **kwargs):
                await self._query.message.reply_document(*args, **kwargs)

        original_message = update.message
        update.message = FakeMessage(query)

        action = query.data.replace('quick_', '')

        try:
            if action == 'stats':
                await self.stats(update, context)
            elif action == 'plan':
                await self.plan(update, context)
            elif action == 'sync':
                await self.sync(update, context)
            elif action == 'calendar':
                await self.calendar(update, context)
            logger.info(f"Пользователь {update.effective_user.id} использовал quick action: {action}")
        except Exception as e:
            logger.error(f"❌ ОШИБКА в quick action '{action}': {e}")
            import traceback
            logger.error(traceback.format_exc())
            await query.message.reply_text(f"❌ Ошибка: {e}")
        finally:
            update.message = original_message

    async def debug_callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Debug: ловит все неперехваченные callbacks"""
        query = update.callback_query
        logger.warning(f"⚠️ НЕПЕРЕХВАЧЕННЫЙ CALLBACK: user={update.effective_user.id}, data='{query.data}'")
        await query.answer("Debug: этот callback не обработан")

    async def ask_plan_days(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало создания плана - выбор дней недели"""
        from datetime import date

        query = update.callback_query
        await query.answer()

        # Определяем цель
        goal_mapping = {
            'plan_tarki': {'name': 'Тарки-Тау 50км', 'distance': 50, 'date': date(2026, 2, 15)},
            'plan_marathon': {'name': 'Марафон 42км', 'distance': 42, 'date': date(2026, 3, 15)},
            'plan_dwt': {'name': 'DWT 65км', 'distance': 65, 'date': date(2026, 4, 15)}
        }

        goal_data = goal_mapping.get(query.data)

        if not goal_data:
            await query.edit_message_text("❌ Неизвестная цель")
            return ConversationHandler.END

        # Сохраняем цель в контекст
        context.user_data['goal_data'] = goal_data
        context.user_data['selected_days'] = []

        # Кнопки для выбора дней недели
        keyboard = [
            [
                InlineKeyboardButton("Пн", callback_data="days_1"),
                InlineKeyboardButton("Вт", callback_data="days_2"),
                InlineKeyboardButton("Ср", callback_data="days_3")
            ],
            [
                InlineKeyboardButton("Чт", callback_data="days_4"),
                InlineKeyboardButton("Пт", callback_data="days_5"),
                InlineKeyboardButton("Сб", callback_data="days_6"),
                InlineKeyboardButton("Вс", callback_data="days_7")
            ],
            [InlineKeyboardButton("✅ Готово", callback_data="days_done")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"🎯 Цель: {goal_data['name']}\n\n"
            "📅 Выбери дни недели, в которые ты можешь тренироваться:\n"
            "(Нажми на дни, затем нажми ✅ Готово)\n\n"
            "Выбрано: —",
            reply_markup=reply_markup
        )

        return PLAN_DAYS

    async def receive_plan_days(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение выбранных дней недели"""
        query = update.callback_query
        await query.answer()

        if query.data == "days_done":
            selected_days = context.user_data.get('selected_days', [])

            if len(selected_days) < 2:
                await query.answer("❌ Выбери минимум 2 дня для тренировок", show_alert=True)
                return PLAN_DAYS

            goal_data = context.user_data.get('goal_data')

            await query.edit_message_text(
                f"🎯 Цель: {goal_data['name']}\n"
                f"📅 Дни тренировок: {len(selected_days)} дней\n\n"
                "⏱ Сколько минут готов заниматься на тренировке?\n\n"
                "Напиши число (например: 60, 90, 120)\n\n"
                "Или отправь /cancel для отмены"
            )

            return PLAN_TIME

        # Обработка выбора дня
        day_num = int(query.data.replace('days_', ''))
        selected_days = context.user_data.get('selected_days', [])

        if day_num in selected_days:
            selected_days.remove(day_num)
        else:
            selected_days.append(day_num)

        context.user_data['selected_days'] = selected_days

        # Обновляем текст с выбранными днями
        days_names = {1: "Пн", 2: "Вт", 3: "Ср", 4: "Чт", 5: "Пт", 6: "Сб", 7: "Вс"}
        selected_names = ", ".join([days_names[d] for d in sorted(selected_days)])

        goal_data = context.user_data.get('goal_data')

        # Кнопки для выбора дней (помечаем выбранные)
        keyboard = [
            [
                InlineKeyboardButton(f"{'✅ ' if 1 in selected_days else ''}Пн", callback_data="days_1"),
                InlineKeyboardButton(f"{'✅ ' if 2 in selected_days else ''}Вт", callback_data="days_2"),
                InlineKeyboardButton(f"{'✅ ' if 3 in selected_days else ''}Ср", callback_data="days_3")
            ],
            [
                InlineKeyboardButton(f"{'✅ ' if 4 in selected_days else ''}Чт", callback_data="days_4"),
                InlineKeyboardButton(f"{'✅ ' if 5 in selected_days else ''}Пт", callback_data="days_5"),
                InlineKeyboardButton(f"{'✅ ' if 6 in selected_days else ''}Сб", callback_data="days_6"),
                InlineKeyboardButton(f"{'✅ ' if 7 in selected_days else ''}Вс", callback_data="days_7")
            ],
            [InlineKeyboardButton("✅ Готово", callback_data="days_done")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"🎯 Цель: {goal_data['name']}\n\n"
            "📅 Выбери дни недели, в которые ты можешь тренироваться:\n"
            "(Нажми на дни, затем нажми ✅ Готово)\n\n"
            f"Выбрано: {selected_names if selected_names else '—'}",
            reply_markup=reply_markup
        )

        return PLAN_DAYS

    async def receive_plan_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение времени на тренировку и генерация плана"""
        from datetime import date
        from ..core.plan_generator import PlanGenerator

        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        # Парсим введённое время
        try:
            time_min = int(update.message.text.strip())

            if time_min < 30 or time_min > 300:
                await update.message.reply_text(
                    "❌ Время должно быть от 30 до 300 минут\n\n"
                    "Попробуй ещё раз или отправь /cancel"
                )
                return PLAN_TIME

        except ValueError:
            await update.message.reply_text(
                "❌ Не могу распознать число\n\n"
                "Напиши просто число (например: 60, 90, 120)\n"
                "Или отправь /cancel для отмены"
            )
            return PLAN_TIME

        # Получаем сохранённые данные
        goal_data = context.user_data.get('goal_data')
        selected_days = context.user_data.get('selected_days', [])

        await update.message.reply_text(
            f"⏳ Генерирую индивидуальный план...\n\n"
            f"🎯 Цель: {goal_data['name']}\n"
            f"📅 Дней в неделю: {len(selected_days)}\n"
            f"⏱ Время на тренировку: {time_min} мин"
        )

        # Генерируем план
        generator = PlanGenerator(user.id)
        trainings = generator.generate_detailed_plan(
            goal_distance=goal_data['distance'],
            goal_date=goal_data['date'],
            training_days=selected_days,
            time_per_session=time_min,
            weeks=4
        )

        # Сохраняем в БД
        count = generator.save_plan_to_db(trainings)

        await update.message.reply_text(
            f"✅ План создан!\n\n"
            f"🎯 Цель: {goal_data['name']} ({goal_data['date'].strftime('%d.%m.%Y')})\n"
            f"📅 Сгенерировано тренировок: {count}\n"
            f"📆 Период: 4 недели\n\n"
            "Используй /plan чтобы посмотреть план на неделю"
        )

        logger.info(f"Пользователь {telegram_id} создал индивидуальный план для {goal_data['name']}")
        return ConversationHandler.END

    async def cancel_plan_creation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена создания плана"""
        await update.message.reply_text(
            "❌ Создание плана отменено\n\n"
            "Используй /plan чтобы начать заново"
        )
        return ConversationHandler.END

    async def register_commands(self):
        """Регистрация команд бота в BotFather"""
        from telegram import BotCommand

        commands = [
            BotCommand("start", "Начало работы"),
            BotCommand("help", "Помощь"),
            BotCommand("sync", "Синхронизация с Garmin"),
            BotCommand("stats", "Статистика за неделю/месяц"),
            BotCommand("plan", "План тренировок на неделю"),
            BotCommand("calendar", "Скачать план для календаря"),
        ]

        try:
            await self.app.bot.set_my_commands(commands)
            logger.info(f"✅ Зарегистрировано {len(commands)} команд")
        except Exception as e:
            logger.error(f"❌ Ошибка регистрации команд: {e}")

    def run(self):
        """Запуск бота"""
        try:
            logger.info("🚀 Бот запущен")

            # Регистрируем команды при запуске
            async def post_init(app):
                await self.register_commands()

            self.app.post_init = post_init

            self.app.run_polling(allowed_updates=Update.ALL_TYPES)
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Telegram API: {e}")
            raise

    def stop(self):
        """Остановка бота"""
        for user_id, user_scheduler in self.user_schedulers.items():
            try:
                user_scheduler.stop()
                logger.info(f"Scheduler остановлен для пользователя {user_id}")
            except Exception as e:
                logger.error(f"Ошибка остановки scheduler для {user_id}: {e}")
        logger.info("⏹️  Бот остановлен")
