"""Telegram бот"""
from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from telegram import Update
from telegram.ext import Application
from telegram.ext import CallbackQueryHandler
from telegram.ext import CommandHandler
from telegram.ext import ContextTypes
from telegram.ext import ConversationHandler
from telegram.ext import MessageHandler
from telegram.ext import filters

from ..core.ai_training_analyzer import get_training_analyzer
from ..core.hr_zones import format_hr_zones_summary
from ..core.personal_records import create_records_manager
from ..core.plan_adapter import PlanAdapter
from ..core.reminders import get_reminder_scheduler
from ..core.reminders import init_reminder_scheduler
from ..core.scheduler import TrainingScheduler
from ..core.stats_calculator import StatsCalculator
from ..core.vdot_calculator import calculate_best_vdot
from ..core.vdot_calculator import format_vdot_summary
from ..core.wellness_survey import WellnessSurvey
from ..database.db import db
from ..integrations.calendar_sync import calendar_sync
from ..integrations.garmin_sync import garmin_sync
from ..utils import time_utils
from ..utils.config import Config
from ..utils.logger import logger

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
        self.reminder_scheduler = None  # Будет инициализирован в run()
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
        self.app.add_handler(CommandHandler("records", self.records))
        self.app.add_handler(CommandHandler("plan", self.plan))
        self.app.add_handler(CommandHandler("calendar", self.calendar))
        self.app.add_handler(CommandHandler("skip", self.skip_training))
        self.app.add_handler(CommandHandler("set_google_token", self.set_google_token))
        self.app.add_handler(CommandHandler("reset", self.reset_user))
        self.app.add_handler(CommandHandler("zones", self.zones_command))
        self.app.add_handler(CommandHandler("methodology", self.methodology_command))

        # ВАЖНО: Standalone CallbackQueryHandlers ДО ConversationHandlers
        # чтобы они не были заблокированы
        self.app.add_handler(CallbackQueryHandler(self.handle_survey_callback, pattern="^survey_"))
        self.app.add_handler(CallbackQueryHandler(self.handle_no_garmin_account, pattern="^no_garmin_account$"))
        self.app.add_handler(CallbackQueryHandler(self.handle_google_calendar_setup, pattern="^setup_google_calendar$"))
        self.app.add_handler(CallbackQueryHandler(self.handle_start_onboarding, pattern="^start_onboarding$"))
        self.app.add_handler(CallbackQueryHandler(self.handle_goal_selection, pattern="^goal_"))
        self.app.add_handler(CallbackQueryHandler(self.handle_race_type_selection, pattern="^racetype_"))
        self.app.add_handler(CallbackQueryHandler(self.handle_distance_selection, pattern="^distance_"))
        self.app.add_handler(CallbackQueryHandler(self.handle_days_selection, pattern="^trainday_"))
        self.app.add_handler(CallbackQueryHandler(self.handle_level_onboarding, pattern="^level_onboarding_"))
        self.app.add_handler(CallbackQueryHandler(self.handle_level_selection, pattern="^level_"))
        self.app.add_handler(CallbackQueryHandler(self.handle_start_time_selection, pattern="^starttime_"))
        self.app.add_handler(CallbackQueryHandler(self.handle_reset_confirm, pattern="^(confirm|cancel)_reset$"))
        self.app.add_handler(CallbackQueryHandler(self.handle_quick_actions, pattern="^quick_"))
        self.app.add_handler(CallbackQueryHandler(self.handle_stats_period, pattern="^stats_"))
        self.app.add_handler(CallbackQueryHandler(self.handle_next_3_trainings, pattern="^next3_"))

        # ConversationHandlers после standalone handlers
        self.app.add_handler(garmin_registration_handler)
        self.app.add_handler(plan_creation_handler)
        # Debug: catch-all handler для неперехваченных callbacks
        self.app.add_handler(CallbackQueryHandler(self.debug_callback_handler))
        # AI-чат: обработка текстовых сообщений (после всех команд и ConversationHandlers)
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_ai_chat))
        logger.info("Обработчики команд настроены")

    async def send_notification_message(self, telegram_id: int, message: str):
        """
        Отправить уведомление пользователю

        Args:
            telegram_id: Telegram ID пользователя
            message: Текст сообщения
        """
        try:
            await self.app.bot.send_message(chat_id=telegram_id, text=message)
            logger.info(f"✉️ Уведомление отправлено telegram_id={telegram_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления telegram_id={telegram_id}: {e}")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        # Проверяем есть ли учетные данные Garmin
        credentials = db.get_user_garmin_credentials(user.id)

        if not credentials:
            # Новый пользователь - запрашиваем регистрацию
            keyboard = [
                [InlineKeyboardButton("✅ Есть аккаунт Garmin   ", callback_data="register_garmin")],
                [InlineKeyboardButton("❌ Создать новый аккаунт ", callback_data="no_garmin_account")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            welcome_text = """
🏃 Привет! Я твой бот-тренер по бегу.

Помогу подготовиться к забегам и адаптировать
тренировки под твой уровень.

Для работы мне нужен доступ к твоим тренировкам
в Garmin Connect.

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

        # Получаем рекомендацию на сегодня
        daily_rec = self._get_daily_recommendation(user.id)

        welcome_text = "🏃 С возвращением!"

        if daily_rec:
            welcome_text += daily_rec

        welcome_text += """

Команды: /sync /stats /plan /calendar /zones /methodology
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
/zones — Персональные зоны пульса
/methodology — Методология расчёта темпов

✅ Реализовано:
• Автоматическая синхронизация Garmin
• Персонализация по VDOT и LTHR
• Адаптивный план тренировок
• Вечерний опрос самочувствия
• Экспорт плана в календарь
• Пропуск тренировок с адаптацией
"""
        await update.message.reply_text(help_text)

    async def zones_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /zones - показать персональные зоны пульса"""
        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)
        settings = db.get_user_settings(user.id)

        lthr = settings.get('lthr') if settings else None

        if not lthr:
            await update.message.reply_text(
                "Зоны пульса пока не рассчитаны.\n\n"
                "Для расчёта нужен LTHR (пульс лактатного порога) из Garmin.\n"
                "Используй /sync для синхронизации данных."
            )
            return

        zones_text = format_hr_zones_summary(lthr)
        await update.message.reply_text(zones_text, parse_mode='Markdown')

    async def methodology_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /methodology - показать методологию расчёта темпов"""
        from ..core.vdot_calculator import get_training_paces

        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)
        settings = db.get_user_settings(user.id)

        vdot = settings.get('vdot') if settings else None
        vdot_source = settings.get('vdot_source') if settings else None
        lthr = settings.get('lthr') if settings else None

        if not vdot and not lthr:
            await update.message.reply_text(
                "Персонализация пока не настроена.\n\n"
                "Для расчёта персональных темпов нужны:\n"
                "• VDOT — рассчитывается по твоим рекордам на 5K/10K/полумарафон/марафон\n"
                "• LTHR — пульс лактатного порога из Garmin\n\n"
                "Используй /sync для синхронизации данных."
            )
            return

        lines = ["**Методология персонализации**\n"]

        if vdot:
            lines.append(f"**VDOT: {vdot:.1f}** (Jack Daniels)")
            if vdot_source:
                lines.append(f"Источник: результат на {vdot_source.upper()}\n")

            paces = get_training_paces(vdot)
            if paces:
                lines.append("**Тренировочные темпы:**")
                lines.append(f"• Easy (лёгкий): {paces.get('E', 'N/A')}")
                lines.append(f"• Marathon (марафонский): {paces.get('M', 'N/A')}")
                lines.append(f"• Threshold (пороговый): {paces.get('T', 'N/A')}")
                lines.append(f"• Interval (интервальный): {paces.get('I', 'N/A')}")
                lines.append(f"• Repetition (повторы): {paces.get('R', 'N/A')}")
                lines.append("")

        if lthr:
            lines.append(f"**LTHR: {lthr} уд/мин** (Joe Friel)")
            lines.append("Зоны пульса рассчитаны по LTHR.")
            lines.append("Используй /zones для просмотра.\n")

        lines.append("**Принципы плана:**")
        lines.append("• 80/20: 80% лёгких, 20% интенсивных тренировок")
        lines.append("• Разгрузочная неделя каждые 3-4 недели (-25%)")
        lines.append("• Оптимальные интервалы VO2max: 4-6x5 мин")

        await update.message.reply_text("\n".join(lines), parse_mode='Markdown')

    async def sync(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /sync - ручная синхронизация с Garmin"""

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

        # Получаем текущий VDOT для сравнения
        old_settings = db.get_user_settings(user.id)
        old_vdot = old_settings.get('vdot') if old_settings else None

        await update.message.reply_text("📥 Синхронизирую тренировки за последние 60 дней + физиологические данные...")

        try:
            # Авторизуемся в Garmin
            email, password = credentials
            if not garmin_sync.login(email, password):
                await update.message.reply_text("❌ Не удалось авторизоваться в Garmin")
                return

            # Синхронизируем 60 дней + LTHR + Personal Records
            total_count, lthr, personal_records = garmin_sync.sync_last_60_days(user.id)

            # Рассчитываем VDOT по персональным рекордам
            vdot, vdot_source, vdot_time = calculate_best_vdot(personal_records) if personal_records else (None, None, None)

            # Сохраняем физиологические данные
            if lthr or vdot:
                db.save_user_physiology(
                    user.id,
                    lthr=lthr,
                    vdot=vdot,
                    vdot_source=vdot_source,
                    vdot_time_seconds=vdot_time
                )

            # Формируем ответ пользователю
            result_lines = []
            if total_count > 0:
                result_lines.append(f"✅ Загружено {total_count} тренировок за 60 дней                    ")
            else:
                result_lines.append("ℹ️ Новых тренировок не найдено                                    ")

            if lthr:
                result_lines.append("\n**Физиологические данные:**                                      ")
                result_lines.append(f"- LTHR: {lthr} уд/мин                                                ")

            # Проверяем рост VDOT
            vdot_changed = False
            if vdot:
                if old_vdot and vdot > old_vdot:
                    delta = vdot - old_vdot
                    result_lines.append(f"- VDOT: {vdot:.0f} (было {old_vdot:.0f}, **+{delta:.1f}**)                ")
                    vdot_changed = True
                else:
                    result_lines.append(f"- VDOT: {vdot:.0f} (по {vdot_source})                              ")

            await update.message.reply_text("\n".join(result_lines), parse_mode='Markdown')

            # Если VDOT вырос — показываем обновлённые темпы
            if vdot_changed:
                from ..core.vdot_calculator import get_training_paces
                paces = get_training_paces(vdot)
                if paces:
                    pace_text = "🚀 **Темпы пересчитаны!**\n\n"
                    pace_text += f"• Easy: {paces.get('E', 'N/A')}\n"
                    pace_text += f"• Threshold: {paces.get('T', 'N/A')}\n"
                    pace_text += f"• Interval: {paces.get('I', 'N/A')}\n"
                    pace_text += "\nНовые темпы применяются к будущим тренировкам"
                    await update.message.reply_text(pace_text, parse_mode='Markdown')

            # Если VDOT новый (не было раньше), показываем саммари
            elif vdot and vdot_source and vdot_time and not old_vdot:
                summary = format_vdot_summary(vdot, vdot_source, vdot_time)
                await update.message.reply_text(summary, parse_mode='Markdown')

            if total_count > 0:

                # AI-анализ последней тренировки
                latest_training = db.get_latest_training(user.id)
                if latest_training:
                    await update.message.reply_text("🤖 Анализирую последнюю тренировку...")

                    # Получаем цель пользователя для контекста
                    user_goal = db.get_user_settings(user.id)

                    # Запрашиваем AI-анализ
                    analyzer = get_training_analyzer()
                    analysis = analyzer.analyze_training(latest_training, user_goal)

                    await update.message.reply_text(f"📊 Анализ тренировки:\n\n{analysis}")

                    # Проверяем персональные рекорды
                    records_manager = create_records_manager(user.id)
                    new_records = records_manager.check_training_for_records(latest_training)

                    if new_records:
                        records_text = "🏆 Новый персональный рекорд!\n\n"
                        for record in new_records:
                            records_text += f"{record['name']}: {record['value']} {record['unit']}\n"
                        records_text += "\nПоздравляю! Продолжай в том же духе! 💪"
                        await update.message.reply_text(records_text)
            else:
                await update.message.reply_text("ℹ️ Новых тренировок за последние 14 дней не найдено")
        except Exception as e:
            logger.error(f"Ошибка синхронизации для {telegram_id}: {e}")
            await update.message.reply_text(
                "❌ Ошибка синхронизации с Garmin.\n\n"
                "Проверь правильность логина/пароля в настройках аккаунта Garmin"
            )

    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /stats - выбор периода статистики"""
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

        # Показываем кнопки выбора периода
        keyboard = [
            [
                InlineKeyboardButton("📅 Неделя", callback_data="stats_week"),
                InlineKeyboardButton("📅 Месяц", callback_data="stats_month")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "📊 Выбери период для статистики:                             ",
            reply_markup=reply_markup
        )

    async def handle_stats_period(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора периода статистики"""
        query = update.callback_query
        await query.answer()

        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        # Создаём калькулятор
        calculator = StatsCalculator(user.id)

        period = query.data.replace("stats_", "")  # week или month

        # Получаем статистику и форматируем объединённо
        if period == "month":
            stats = calculator.get_month_stats()
            stats_text = calculator.format_combined_stats(stats, period="month")
        else:  # week
            stats = calculator.get_week_stats()
            stats_text = calculator.format_combined_stats(stats, period="week")

        # Добавляем кнопки переключения периода
        keyboard = [
            [
                InlineKeyboardButton("📅 Неделя", callback_data="stats_week"),
                InlineKeyboardButton("📅 Месяц", callback_data="stats_month")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            stats_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

        logger.info(f"Пользователь {telegram_id} запросил объединённую статистику за {period}")

    async def handle_next_3_trainings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка кнопки 'Следующие 3 тренировки'"""
        from datetime import date
        from datetime import timedelta

        query = update.callback_query
        await query.answer()

        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        # Извлекаем дату из callback_data (формат: "next3_2026-01-31")
        current_date_str = query.data.replace("next3_", "")
        current_date = date.fromisoformat(current_date_str)

        # Получаем тренировки после текущей даты (следующие 30 дней)
        next_day = current_date + timedelta(days=1)
        end_date = current_date + timedelta(days=30)
        future_plans = db.get_plan_for_period(user.id, next_day, end_date)

        if not future_plans or len(future_plans) == 0:
            await query.edit_message_reply_markup(reply_markup=None)
            await context.bot.send_message(
                chat_id=telegram_id,
                text="ℹ️ Следующих тренировок не найдено"
            )
            return

        # Берём первые 3
        next_3 = future_plans[:3]

        # Получаем настройки времени старта
        settings = db.get_user_settings(user.id)
        start_time_weekday = settings.get('start_time_weekday', '07:00') if settings else '07:00'
        start_time_weekend = settings.get('start_time_weekend', '09:00') if settings else '09:00'

        # Формируем сообщение
        days_ru = {
            0: "Понедельник", 1: "Вторник", 2: "Среда", 3: "Четверг",
            4: "Пятница", 5: "Суббота", 6: "Воскресенье"
        }

        message_text = "📅 **Следующие 3 тренировки:**\n\n"

        for i, plan in enumerate(next_3, 1):
            day_name = days_ru.get(plan.date.weekday(), "")
            is_weekend = plan.date.weekday() >= 5
            start_time = start_time_weekend if is_weekend else start_time_weekday

            message_text += f"**{i}. {day_name} {plan.date.strftime('%d.%m')}** | Старт: {start_time}\n"

            if hasattr(plan, 'goal') and plan.goal:
                message_text += f"🎯 {plan.goal}\n"

            if plan.description:
                message_text += f"{plan.description}\n"
            else:
                message_text += f"**{plan.type.capitalize()}**\n"
                if plan.duration_min:
                    message_text += f"- Время: {plan.duration_min} мин\n"
                if plan.distance_km:
                    message_text += f"- Расстояние: ~{plan.distance_km:.1f} км\n"
                if plan.target_zone:
                    message_text += f"- Зоны: {plan.target_zone}\n"

            message_text += "\n"

        # Удаляем кнопку с исходного сообщения
        await query.edit_message_reply_markup(reply_markup=None)

        # Отправляем следующие тренировки
        await context.bot.send_message(
            chat_id=telegram_id,
            text=message_text,
            parse_mode='Markdown'
        )

        logger.info(f"Показаны следующие 3 тренировки для user={telegram_id} после {current_date}")

    async def records(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /records - показ персональных рекордов"""
        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        # Проверяем есть ли credentials
        credentials = db.get_user_garmin_credentials(user.id)
        if not credentials:
            await update.message.reply_text(
                "🏆 Персональные рекорды недоступны\n\n"
                "❌ Учетные данные Garmin не найдены.\n\n"
                "Используй /start для регистрации"
            )
            return

        # Получаем рекорды
        records_manager = create_records_manager(user.id)
        records_text = records_manager.format_records_message()

        await update.message.reply_text(records_text)
        logger.info(f"Пользователь {telegram_id} запросил персональные рекорды")

    async def plan(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /plan - показ плана на неделю"""
        from datetime import timedelta

        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        # Определяем начало текущей недели (понедельник)
        today = time_utils.today()
        start_of_week = today - timedelta(days=today.weekday())

        # Получаем план на неделю
        plans = db.get_plan_for_week(user.id, start_of_week)

        if not plans:
            # Проверяем есть ли данные для автосоздания плана
            settings = db.get_user_settings(user.id)

            if settings and settings.get('goal_date') and settings.get('training_days') and settings.get('goal_type') in ['race', 'trail']:
                # Автосоздаем план используя данные из онбординга
                await update.message.reply_text(
                    "📅 План не найден.\n\n"
                    "⏳ Создаю план на основе твоих настроек..."
                )

                plan_created = await self._auto_create_race_plan(user.id, update.message)

                if plan_created:
                    # Получаем созданный план и показываем
                    plans = db.get_plan_for_week(user.id, start_of_week)
                    if plans:
                        await update.message.reply_text("✅ План создан! Вот он:")
                    else:
                        await update.message.reply_text("✅ План создан, но для текущей недели нет тренировок.\n\nИспользуй /plan на следующей неделе.")
                        return
                else:
                    await update.message.reply_text(
                        "❌ Не удалось создать план автоматически.\n\n"
                        "Проверь что указаны все настройки (дата забега, дни тренировок)."
                    )
                    return
            else:
                # Нет данных для автосоздания - предлагаем пройти онбординг
                await update.message.reply_text(
                    "📅 План тренировок не найден.\n\n"
                    "Для создания плана нужно настроить цель и дни тренировок.\n\n"
                    "Используй /start для настройки или /help для помощи."
                )
                return

        # Если после автосоздания плана нет на эту неделю - выходим
        if not plans:
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

        # Получаем настройки времени старта
        settings = db.get_user_settings(user.id)
        start_time_weekday = settings.get('start_time_weekday', '07:00') if settings else '07:00'
        start_time_weekend = settings.get('start_time_weekend', '09:00') if settings else '09:00'

        for plan in plans:
            day_name = days_ru.get(plan.date.weekday(), "")
            is_weekend = plan.date.weekday() >= 5
            start_time = start_time_weekend if is_weekend else start_time_weekday

            # Формируем детальное сообщение для тренировки
            plan_text = f"**{day_name} {plan.date.strftime('%d.%m')}** | Старт: {start_time}\n\n"

            # Добавляем цель тренировки
            if hasattr(plan, 'goal') and plan.goal:
                plan_text += f"🎯 {plan.goal}\n\n"

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

            # Кнопка "Следующие 3 тренировки"
            keyboard = [[InlineKeyboardButton("📅 Следующие 3 тренировки", callback_data=f"next3_{plan.date.isoformat()}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(plan_text, parse_mode='Markdown', reply_markup=reply_markup)

        logger.info(f"Пользователь {telegram_id} запросил план на неделю")

    async def calendar(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /calendar - экспорт плана в ICS файл для импорта в календарь"""
        from datetime import timedelta

        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        # Определяем начало текущей недели
        today = time_utils.today()
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
        from datetime import datetime

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
                    skip_date = datetime.strptime(f"{date_str}.{time_utils.today().year}", "%d.%m.%Y").date()
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
            skip_date = time_utils.today()

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
        from datetime import timedelta

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
                    yesterday = time_utils.today() - timedelta(days=1)
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
        except Exception:
            pass

        # Отправляем сообщение о начале синхронизации и сохраняем его
        status_message = await update.message.reply_text(
            "✅ Регистрация завершена!\n\n"
            "Теперь я могу автоматически синхронизировать твои тренировки с Garmin.\n\n"
            "Синхронизирую твои последние тренировки...\n"
            "Подожди 2-5 минут ⏳"
        )

        # Запускаем первую синхронизацию (60 дней + LTHR + VDOT)
        user = db.get_or_create_user(telegram_id)
        try:
            # ✅ Авторизуемся с credentials нового пользователя
            if not garmin_sync.login(email, password):
                await status_message.edit_text(
                    "❌ Не удалось авторизоваться в Garmin.\n\n"
                    "Проверь правильность email и пароля.\n\n"
                    "Используй /start для повторной попытки"
                )
                return ConversationHandler.END

            # Синхронизируем 60 дней + получаем физиологические данные
            total_count, lthr, personal_records = garmin_sync.sync_last_60_days(user.id)

            # Рассчитываем VDOT
            vdot, vdot_source, vdot_time = calculate_best_vdot(personal_records) if personal_records else (None, None, None)

            # Сохраняем физиологические данные
            if lthr or vdot:
                db.save_user_physiology(
                    user.id,
                    lthr=lthr,
                    vdot=vdot,
                    vdot_source=vdot_source,
                    vdot_time_seconds=vdot_time
                )

            # Формируем ответ
            result_lines = []
            if total_count > 0:
                result_lines.append(f"✅ Загружено {total_count} тренировок за 60 дней                    ")
            else:
                result_lines.append("ℹ️ Тренировок за последние 60 дней не найдено          ")

            if lthr or vdot:
                result_lines.append("\n**Персонализация:**                                      ")
                if lthr:
                    result_lines.append(f"- LTHR: {lthr} уд/мин (зоны пульса рассчитаны)                ")
                if vdot:
                    result_lines.append(f"- VDOT: {vdot:.0f} (темпы рассчитаны по {vdot_source})              ")
                result_lines.append("\nТвой план будет персонализирован!                        ")

            # Добавляем призыв к действию
            result_lines.append("\n▶️ Настроим план тренировок                              ")

            # Кнопки для следующего шага (в одну строку)
            keyboard = [
                [
                    InlineKeyboardButton("📅 Календарь", callback_data="setup_google_calendar"),
                    InlineKeyboardButton("⏭ Настройка", callback_data="start_onboarding")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Редактируем сообщение с результатом + кнопками
            await status_message.edit_text(
                "\n".join(result_lines),
                parse_mode='Markdown',
                reply_markup=reply_markup
            )

            # Показываем темпы если есть VDOT (отдельным сообщением)
            if vdot and vdot_source and vdot_time:
                summary = format_vdot_summary(vdot, vdot_source, vdot_time)
                await update.message.reply_text(summary, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Ошибка первой синхронизации: {e}")
            # Редактируем сообщение с ошибкой
            await status_message.edit_text(
                "⚠️ Не удалось синхронизировать тренировки.\n\n"
                "Проверь правильность логина/пароля и попробуй /sync"
            )

        # Запускаем scheduler для пользователя
        if user.id not in self.user_schedulers:
            user_scheduler = TrainingScheduler(telegram_bot=self.app.bot)
            user_scheduler.start(user.id, telegram_id)
            self.user_schedulers[user.id] = user_scheduler

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

    async def handle_google_calendar_setup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка кнопки подключения календаря — подписка по URL"""
        query = update.callback_query
        telegram_id = update.effective_user.id
        logger.info(f"🔵 handle_google_calendar_setup: user={telegram_id}")

        await query.answer("Генерирую ссылку...")

        # Получаем пользователя и генерируем токен
        user = db.get_or_create_user(telegram_id)
        token = db.get_or_create_calendar_token(user.id)

        # Формируем URL (Railway domain или localhost для теста)
        import os
        railway_domain = os.getenv('RAILWAY_PUBLIC_DOMAIN')
        if railway_domain:
            base_url = f"https://{railway_domain}"
        else:
            base_url = "https://training-bot-production.up.railway.app"  # fallback

        calendar_url = f"{base_url}/calendar/{token}.ics"

        # Отправляем инструкцию
        await query.message.reply_text(
            "📅 Подписка на календарь тренировок\n\n"
            "Твоя персональная ссылка:\n"
            f"`{calendar_url}`\n\n"
            "**Как добавить в iPhone:**\n"
            "1. Скопируй ссылку выше\n"
            "2. Настройки → Календарь → Учётные записи\n"
            "3. Добавить → Подписка на календарь\n"
            "4. Вставь ссылку\n\n"
            "**Как добавить в Google Calendar:**\n"
            "1. calendar.google.com → Другие календари → +\n"
            "2. По URL → Вставь ссылку\n\n"
            "Календарь будет автоматически обновляться!",
            parse_mode='Markdown'
        )

        logger.info(f"✅ Calendar URL отправлен user={telegram_id}")

    async def handle_start_onboarding(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало онбординга — выбор типа тренировок"""
        query = update.callback_query
        await query.answer()

        keyboard = [
            [InlineKeyboardButton("🏁 Подготовка к забегу  ", callback_data="goal_race")],
            [InlineKeyboardButton("🏃 Для здоровья и фитнеса", callback_data="goal_fitness")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.reply_text(
            "🎯 Какая у тебя цель?                                        \n\n"
            "Выбери направление:                                          ",
            reply_markup=reply_markup
        )

    async def handle_goal_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора цели: забег или для себя"""
        query = update.callback_query
        await query.answer()

        goal_type = query.data.replace("goal_", "")
        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        # Сохраняем цель и в context для последующих вызовов
        context.user_data['goal_type'] = goal_type
        db.save_user_goal(user.id, goal_type=goal_type)

        if goal_type == "race":
            # Для забега — выбор типа (шоссе/трейл)
            keyboard = [
                [
                    InlineKeyboardButton("🏃 Полумарафон 21км", callback_data="racetype_half"),
                    InlineKeyboardButton("🏃 Марафон 42км    ", callback_data="racetype_marathon")
                ],
                [
                    InlineKeyboardButton("📏 Своя дистанция  ", callback_data="racetype_custom"),
                    InlineKeyboardButton("⛰️ Трейл-забег    ", callback_data="racetype_trail")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "🏁 Какой тип забега?                                         ",
                reply_markup=reply_markup
            )

        else:  # fitness — тренировки для себя
            # Сразу к выбору дней
            await self._show_days_selection(query=query, context=context)

        logger.info(f"User {telegram_id} выбрал цель: {goal_type}")

    async def handle_race_type_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора типа забега"""
        query = update.callback_query
        await query.answer()

        race_type = query.data.replace("racetype_", "")
        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        logger.info(f"🔘 RACE TYPE CALLBACK: user={telegram_id}, data='{query.data}', parsed='{race_type}'")

        if race_type == "half":
            db.save_user_goal(user.id, goal_type='race', goal_distance_km=21)
            context.user_data['goal_type'] = 'race'
            await self._ask_goal_date(query=query, context=context)

        elif race_type == "marathon":
            db.save_user_goal(user.id, goal_type='race', goal_distance_km=42)
            context.user_data['goal_type'] = 'race'
            await self._ask_goal_date(query=query, context=context)

        elif race_type == "custom":
            context.user_data['goal_type'] = 'race'
            await query.edit_message_text(
                "📏 Введи дистанцию забега в км\n"
                "(например: 10 или 50):"
            )
            context.user_data['awaiting_custom_distance'] = True
            logger.info(f"Установлен флаг awaiting_custom_distance для user={telegram_id}")

        elif race_type == "trail":
            context.user_data['goal_type'] = 'trail'
            await query.edit_message_text(
                "⛰ Введи дистанцию трейла в км\n"
                "(например: 30 или 100):"
            )
            context.user_data['awaiting_trail_distance'] = True
            logger.info(f"Установлен флаг awaiting_trail_distance для user={telegram_id}")

        else:
            logger.warning(f"⚠️ Неизвестный race_type: {race_type} от user={telegram_id}")
            await query.edit_message_text(
                "❌ Устаревшее сообщение.\n\n"
                "Пожалуйста, сделай /reset и начни заново."
            )
            return

        logger.info(f"User {telegram_id} выбрал тип забега: {race_type}")

    async def _ask_goal_date(self, query=None, message=None, context: ContextTypes.DEFAULT_TYPE = None):
        """Спросить дату забега"""
        text = (
            "📅 Когда у тебя забег?\n\n"
            "Напиши дату в формате ДД.ММ.ГГГГ\n"
            "(например: 15.05.2026 или 01.09.2026):"
        )

        if query:
            await query.edit_message_text(text)
        elif message:
            await message.reply_text(text)

        context.user_data['awaiting_goal_date'] = True
        logger.info("Установлен флаг awaiting_goal_date")

    async def _auto_create_race_plan(self, user_id: int, message) -> bool:
        """
        Автоматическое создание плана тренировок после завершения онбординга

        Args:
            user_id: ID пользователя
            message: Сообщение для отправки статуса

        Returns:
            True если план создан успешно
        """
        from ..core.plan_generator import PlanGenerator

        try:
            # Получаем настройки пользователя
            settings = db.get_user_settings(user_id)
            if not settings:
                logger.warning(f"Нет настроек для автосоздания плана user_id={user_id}")
                return False

            # Проверяем наличие всех необходимых данных
            goal_distance = settings.get('goal_distance_km')
            goal_date = settings.get('goal_date')
            training_days = settings.get('training_days')
            goal_type = settings.get('goal_type', 'race')  # По умолчанию 'race'

            if not goal_distance or not goal_date or not training_days:
                logger.warning(f"Недостаточно данных для плана: distance={goal_distance}, date={goal_date}, days={training_days}")
                return False

            # Преобразуем training_days из ["day_1", "day_2"] в [1, 2]
            day_numbers = []
            for day_str in training_days:
                if isinstance(day_str, str) and day_str.startswith('day_'):
                    day_num = int(day_str.replace('day_', ''))
                    day_numbers.append(day_num)

            if not day_numbers:
                logger.warning(f"Не удалось распарсить дни тренировок: {training_days}")
                return False

            # Определяем время на тренировку
            time_per_session = settings.get('training_time_min', 60)  # По умолчанию 60 минут

            # Валидация (должно быть 30-300 минут)
            if not isinstance(time_per_session, int) or time_per_session < 30 or time_per_session > 300:
                logger.warning(f"Некорректное время тренировки {time_per_session}, использую дефолт 60 мин")
                time_per_session = 60

            # Рассчитываем количество недель до забега
            today = time_utils.today()
            if goal_date <= today:
                logger.warning(f"Дата забега {goal_date} уже прошла")
                return False

            days_until_race = (goal_date - today).days
            weeks_until_race = max(4, min(16, days_until_race // 7))  # от 4 до 16 недель

            await message.reply_text(
                f"⏳ Создаю план подготовки...\n\n"
                f"📅 До забега: {days_until_race} дней ({weeks_until_race} недель)\n"
                f"🎯 Дистанция: {goal_distance} км\n"
                f"📆 Тренировочных дней в неделю: {len(day_numbers)}"
            )

            # Получаем уровень подготовки если указан
            fitness_level = settings.get('fitness_level')

            # Генерируем план
            generator = PlanGenerator(user_id)
            trainings = generator.generate_detailed_plan(
                goal_distance=goal_distance,
                goal_date=goal_date,
                training_days=day_numbers,
                time_per_session=time_per_session,
                weeks=weeks_until_race,
                goal_type=goal_type,
                fitness_level=fitness_level
            )

            # Сохраняем в БД
            count = generator.save_plan_to_db(trainings)

            logger.info(f"✅ Автоплан создан для user={user_id}: {count} тренировок на {weeks_until_race} недель")

            return count > 0

        except Exception as e:
            logger.error(f"Ошибка автосоздания плана для user={user_id}: {e}", exc_info=True)
            return False

    async def _show_days_selection(self, query=None, message=None, context: ContextTypes.DEFAULT_TYPE = None):
        """Показать выбор дней недели"""
        # Инициализируем только если еще не инициализировано
        if 'selected_days' not in context.user_data:
            context.user_data['selected_days'] = []

        keyboard = [
            [
                InlineKeyboardButton("Пн", callback_data="trainday_1"),
                InlineKeyboardButton("Вт", callback_data="trainday_2"),
                InlineKeyboardButton("Ср", callback_data="trainday_3"),
                InlineKeyboardButton("Чт", callback_data="trainday_4")
            ],
            [
                InlineKeyboardButton("Пт", callback_data="trainday_5"),
                InlineKeyboardButton("Сб", callback_data="trainday_6"),
                InlineKeyboardButton("Вс", callback_data="trainday_7")
            ],
            [InlineKeyboardButton("✅ Готово", callback_data="trainday_done")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = (
            "📅 Выбери дни для тренировок:                                \n\n"
            "(нажми на дни, затем \"Готово\")                                \n\n"
            "Выбрано: —                                                   "
        )

        if query:
            # Редактируем существующее сообщение
            await query.edit_message_text(text, reply_markup=reply_markup)
        elif message:
            # Создаем новое сообщение
            await message.reply_text(text, reply_markup=reply_markup)

    async def handle_days_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора дней недели"""
        query = update.callback_query
        await query.answer()

        data = query.data.replace("trainday_", "")
        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        if data == "done":
            selected_days = context.user_data.get('selected_days', [])

            if len(selected_days) < 2:
                await query.answer("Выбери минимум 2 дня", show_alert=True)
                return

            # Сохраняем дни
            goal_type = context.user_data.get('goal_type', 'fitness')
            db.save_user_goal(user.id, goal_type=goal_type, training_days=[f"day_{d}" for d in selected_days])

            # Проверяем есть ли история тренировок за последний месяц
            calculator = StatsCalculator(user.id)
            stats = calculator.get_month_stats()

            if stats['trainings_count'] > 0:
                # Есть история → не спрашиваем уровень, сразу время
                await query.message.reply_text(
                    f"✅ Вижу у тебя есть история тренировок ({stats['trainings_count']} за месяц)\n"
                    f"Автоматически определю уровень подготовки\n\n"
                    "⏱ Сколько времени у тебя на одну тренировку?\n\n"
                    "Напиши в минутах (например: 60, 90, 120)\n"
                    "Или диапазон времени (например: с 19 до 21)"
                )
                context.user_data['awaiting_time'] = True
            else:
                # Нет истории → спрашиваем уровень
                keyboard = [
                    [InlineKeyboardButton("🟢 Новичок в беге        ", callback_data="level_onboarding_beginner")],
                    [InlineKeyboardButton("🟡 Средний уровень       ", callback_data="level_onboarding_intermediate")],
                    [InlineKeyboardButton("🔴 Опытный бегун         ", callback_data="level_onboarding_advanced")]
                ]

                await query.message.reply_text(
                    "🏃 Какой у тебя опыт в беге?                                 \n\n"
                    "Нет истории тренировок, поэтому спрашиваю.                   \n"
                    "Это нужно чтобы подобрать правильный объём и интенсивность тренировок                    ",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            return

        # Toggle дня
        day_num = int(data)
        selected_days = context.user_data.get('selected_days', [])

        if day_num in selected_days:
            selected_days.remove(day_num)
        else:
            selected_days.append(day_num)

        context.user_data['selected_days'] = selected_days

        # Обновляем кнопки
        days_names = {1: "Пн", 2: "Вт", 3: "Ср", 4: "Чт", 5: "Пт", 6: "Сб", 7: "Вс"}
        selected_text = ", ".join([days_names[d] for d in sorted(selected_days)]) or "—"

        keyboard = [
            [
                InlineKeyboardButton(f"{'✅' if 1 in selected_days else ''} Пн", callback_data="trainday_1"),
                InlineKeyboardButton(f"{'✅' if 2 in selected_days else ''} Вт", callback_data="trainday_2"),
                InlineKeyboardButton(f"{'✅' if 3 in selected_days else ''} Ср", callback_data="trainday_3"),
                InlineKeyboardButton(f"{'✅' if 4 in selected_days else ''} Чт", callback_data="trainday_4")
            ],
            [
                InlineKeyboardButton(f"{'✅' if 5 in selected_days else ''} Пт", callback_data="trainday_5"),
                InlineKeyboardButton(f"{'✅' if 6 in selected_days else ''} Сб", callback_data="trainday_6"),
                InlineKeyboardButton(f"{'✅' if 7 in selected_days else ''} Вс", callback_data="trainday_7")
            ],
            [InlineKeyboardButton("✅ Готово", callback_data="trainday_done")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"📅 Выбери дни для тренировок:                                \n\n"
            f"(нажми на дни, затем \"Готово\")                                \n\n"
            f"Выбрано: {selected_text}                                     ",
            reply_markup=reply_markup
        )

        logger.info(f"User {telegram_id} toggle день {day_num}, выбрано: {selected_days}")

    async def handle_distance_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Legacy: обработка выбора дистанции (не используется в новом flow)"""
        query = update.callback_query
        await query.answer()
        logger.warning(f"Legacy handle_distance_selection вызван: {query.data}")

    async def set_google_token(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /set_google_token - сохранение Google refresh token"""
        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        # Получаем токен из аргументов
        if not context.args:
            await update.message.reply_text(
                "❌ Укажи refresh_token:\n"
                "`/set_google_token <твой_токен>`",
                parse_mode='Markdown'
            )
            return

        refresh_token = context.args[0]

        # Сохраняем токен
        success = db.save_user_google_credentials(user.id, refresh_token)

        if success:
            # Удаляем сообщение с токеном для безопасности
            try:
                await update.message.delete()
            except Exception:
                pass

            # Пробуем синхронизировать
            try:
                from ..integrations.google_calendar_api import google_calendar_api
                synced = google_calendar_api.sync_training_plan(user.id)

                await update.message.reply_text(
                    f"✅ Google Calendar подключён!\n\n"
                    f"Синхронизировано {synced} тренировок.\n\n"
                    "Теперь тренировки будут автоматически добавляться в твой календарь "
                    "с напоминаниями за 1 час и 15 минут."
                )
            except Exception as e:
                logger.error(f"Ошибка синхронизации с Google Calendar: {e}")
                await update.message.reply_text(
                    "✅ Токен сохранён!\n\n"
                    "⚠️ Не удалось выполнить первую синхронизацию. "
                    "Проверь токен и попробуй /calendar"
                )
        else:
            await update.message.reply_text("❌ Ошибка сохранения токена. Попробуй позже.")

        logger.info(f"Пользователь {telegram_id} настроил Google Calendar")

    async def reset_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /reset - сброс авторизации для повторного онбординга"""
        telegram_id = update.effective_user.id

        keyboard = [
            [InlineKeyboardButton("✅ Да, сбросить", callback_data="confirm_reset")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_reset")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "⚠️ **Сброс данных**                                         \n\n"
            "Это удалит:                                                 \n"
            "- План тренировок                                           \n"
            "- Настройки цели                                            \n"
            "- Историю тренировок                                        \n\n"
            "**Сохранится:** авторизация Garmin (для удобства теста)     \n\n"
            "Ты уверен?                                                  ",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    async def handle_reset_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка подтверждения сброса"""
        query = update.callback_query
        await query.answer()

        logger.info(f"🔄 handle_reset_confirm вызван, query.data={query.data}")

        if query.data == "confirm_reset":
            telegram_id = update.effective_user.id
            logger.info(f"🔄 Начало сброса для telegram_id={telegram_id}")

            user = db.get_or_create_user(telegram_id)
            logger.info(f"🔄 User получен: user.id={user.id}, onboarding_completed={user.onboarding_completed}")

            # Останавливаем user scheduler если есть
            if user.id in self.user_schedulers:
                try:
                    logger.info(f"🔄 Останавливаем user_scheduler для user.id={user.id}")
                    self.user_schedulers[user.id].stop()
                    del self.user_schedulers[user.id]
                    logger.info(f"✅ Остановлен scheduler для user={user.id}")
                except Exception as e:
                    logger.error(f"❌ Ошибка остановки scheduler для user={user.id}: {e}")
            else:
                logger.info(f"ℹ️ User scheduler не найден для user.id={user.id}")

            # Удаляем напоминания
            logger.info(f"🔄 Удаление напоминаний для user.id={user.id}")
            reminder_scheduler = get_reminder_scheduler()
            if reminder_scheduler:
                removed_count = reminder_scheduler.remove_user_reminders(user.id)
                logger.info(f"✅ Удалено {removed_count} напоминаний для user.id={user.id}")
            else:
                logger.warning("⚠️ ReminderScheduler не инициализирован")

            # Очищаем кешированную сессию Garmin (OAuth tokens)
            # logger.info(f"🔄 Очистка Garmin сессии")
            # garmin_sync.clear_session()  # ЗАКОММЕНТИРОВАНО: сохраняем Garmin авторизацию для тестирования

            # Сбрасываем данные в БД
            logger.info(f"🔄 Вызов db.reset_user для telegram_id={telegram_id}")
            success = db.reset_user(telegram_id)
            logger.info(f"🔄 db.reset_user вернул: {success}")

            if success:
                await query.edit_message_text(
                    "✅ Данные сброшены.\n\n"
                    "Используй /start для повторной регистрации."
                )
                logger.info(f"✅ Пользователь {telegram_id} полностью сбросил данные")
            else:
                logger.error(f"❌ db.reset_user вернул False для telegram_id={telegram_id}")
                await query.edit_message_text("❌ Ошибка сброса. Попробуй позже.")
        else:
            logger.info(f"ℹ️ Сброс отменён пользователем, query.data={query.data}")
            await query.edit_message_text("❌ Сброс отменён.")

    # === Внутренние методы для quick actions ===
    # Эти методы принимают telegram_id и message напрямую,
    # что позволяет вызывать их как из команд, так и из callback кнопок

    def _get_daily_recommendation(self, user_id: int) -> str:
        """
        Получить рекомендацию на сегодня

        Returns:
            Текст рекомендации или пустая строка
        """
        from datetime import timedelta

        today = time_utils.today()

        # Получаем план на сегодня
        today_plan = db.get_plan_for_date(user_id, today)
        if not today_plan:
            return ""

        # Получаем последний wellness опрос
        wellness = db.get_latest_wellness(user_id)

        # Тип тренировки на русском
        type_names = {
            'easy': 'Лёгкая',
            'long': 'Длинная',
            'tempo': 'Темповая',
            'intervals': 'Интервалы',
            'recovery': 'Восстановление'
        }
        type_ru = type_names.get(today_plan.type, today_plan.type)

        recommendation = f"\n\n📅 **Сегодня:** {type_ru}"

        if today_plan.distance_km:
            recommendation += f" • {today_plan.distance_km:.1f} км"
        if today_plan.duration_min:
            recommendation += f" • {today_plan.duration_min} мин"

        # Если есть недавний wellness с проблемами — предупреждаем
        if wellness and wellness.date >= today - timedelta(days=2):
            warnings = []

            if wellness.sleep_quality == 'bad':
                warnings.append("плохой сон")
            if wellness.wellness_rating == 1:
                warnings.append("усталость")
            if wellness.pain_reported:
                warnings.append("боль")

            if warnings:
                recommendation += f"\n⚠️ Учтено: {', '.join(warnings)}"
                recommendation += " — нагрузка снижена"

        # Если интенсивная тренировка — напоминаем
        if today_plan.type in ['intervals', 'tempo']:
            recommendation += "\n💪 Готов к интенсиву?"

        return recommendation

    async def _handle_stats(self, telegram_id: int, message):
        """Внутренняя логика статистики"""
        user = db.get_or_create_user(telegram_id)
        credentials = db.get_user_garmin_credentials(user.id)

        if not credentials:
            await message.reply_text(
                "📊 Статистика недоступна\n\n"
                "❌ Учетные данные Garmin не найдены.\n\n"
                "Используй /start для регистрации, затем посмотри статистику.",
                parse_mode='Markdown'
            )
            return

        calculator = StatsCalculator(user.id)
        stats = calculator.get_week_stats()
        stats_text = calculator.format_stats(stats)
        await message.reply_text(stats_text, parse_mode='Markdown')
        logger.info(f"Пользователь {telegram_id} запросил статистику")

    async def _handle_plan(self, telegram_id: int, message):
        """Внутренняя логика плана"""
        from datetime import timedelta

        user = db.get_or_create_user(telegram_id)
        today = time_utils.today()
        start_of_week = today - timedelta(days=today.weekday())
        plans = db.get_plan_for_week(user.id, start_of_week)

        if not plans:
            keyboard = [
                [InlineKeyboardButton("📅 Тарки-Тау 50км (15 фев)", callback_data="plan_tarki")],
                [InlineKeyboardButton("🏃 Марафон 42км (15 мар)", callback_data="plan_marathon")],
                [InlineKeyboardButton("⛰ DWT 65км (15 апр)", callback_data="plan_dwt")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await message.reply_text(
                "📅 План тренировок не найден.\n\n"
                "Выбери цель для автоматической генерации плана:",
                reply_markup=reply_markup
            )
            return

        await message.reply_text(
            f"📅 **План тренировок на неделю**\n"
            f"({start_of_week.strftime('%d.%m')} - {(start_of_week + timedelta(days=6)).strftime('%d.%m')})\n\n"
            f"Всего тренировок: {len(plans)}",
            parse_mode='Markdown'
        )

        days_ru = {
            0: "Понедельник", 1: "Вторник", 2: "Среда", 3: "Четверг",
            4: "Пятница", 5: "Суббота", 6: "Воскресенье"
        }

        for plan in plans:
            day_name = days_ru.get(plan.date.weekday(), "")
            plan_text = f"**{day_name} {plan.date.strftime('%d.%m')}**\n\n"
            if plan.description:
                plan_text += f"{plan.description}\n"
            else:
                plan_text += f"**{plan.type.capitalize()}**\n"
                if plan.duration_min:
                    plan_text += f"- Время: {plan.duration_min} мин\n"
                if plan.distance_km:
                    plan_text += f"- Расстояние: ~{plan.distance_km:.1f} км\n"
                if plan.target_zone:
                    plan_text += f"- Зоны: {plan.target_zone}\n"

            # Кнопка "Следующие 3 тренировки"
            keyboard = [[InlineKeyboardButton("📅 Следующие 3 тренировки", callback_data=f"next3_{plan.date.isoformat()}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await message.reply_text(plan_text, parse_mode='Markdown', reply_markup=reply_markup)

        logger.info(f"Пользователь {telegram_id} запросил план")

    async def _handle_sync(self, telegram_id: int, message, context):
        """Внутренняя логика синхронизации"""
        from datetime import timedelta

        user = db.get_or_create_user(telegram_id)
        credentials = db.get_user_garmin_credentials(user.id)

        if not credentials:
            await message.reply_text(
                "❌ Учетные данные Garmin не найдены.\n\n"
                "Используй /start для регистрации"
            )
            return

        await message.reply_text("📥 Синхронизирую тренировки за последние 60 дней...                    ")

        try:
            total_count = 0
            today = time_utils.today()
            for i in range(60):
                sync_date = today - timedelta(days=i)
                count = garmin_sync.sync_date_for_user(user.id, sync_date)
                total_count += count

            if total_count > 0:
                await message.reply_text(f"✅ Загружено {total_count} тренировок за последние 60 дней                    ")
            else:
                await message.reply_text("ℹ️ Новых тренировок за последние 60 дней не найдено          ")
        except Exception as e:
            logger.error(f"Ошибка синхронизации для {telegram_id}: {e}")
            await message.reply_text(
                "❌ Ошибка синхронизации с Garmin.\n\n"
                "Проверь правильность логина/пароля в настройках аккаунта Garmin"
            )

    async def _handle_calendar(self, telegram_id: int, message):
        """Внутренняя логика календаря"""
        from datetime import timedelta

        user = db.get_or_create_user(telegram_id)
        today = time_utils.today()
        start_of_week = today - timedelta(days=today.weekday())
        plans = db.get_plan_for_week(user.id, start_of_week)

        if not plans:
            await message.reply_text(
                "📅 План тренировок не найден.\n\n"
                "Создай план командой /plan, затем экспортируй в календарь.",
                parse_mode='Markdown'
            )
            return

        await message.reply_text("📅 Генерирую ICS файл для импорта в календарь...")

        try:
            ics_path = calendar_sync.generate_ics_file(user.id, start_of_week, weeks=1)

            if ics_path:
                with open(ics_path, 'rb') as ics_file:
                    await message.reply_document(
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
                            "3. Настройки → Импорт\n\n"
                        ),
                        parse_mode='Markdown'
                    )
                logger.info(f"Отправлен ICS файл пользователю {telegram_id}")
            else:
                await message.reply_text("❌ Ошибка генерации ICS файла")
        except Exception as e:
            logger.error(f"Ошибка генерации ICS для {telegram_id}: {e}")
            await message.reply_text(f"❌ Ошибка: {e}")

    async def handle_quick_actions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка quick action кнопок"""
        query = update.callback_query
        logger.info(f"🔘 QUICK ACTION: user={update.effective_user.id}, data='{query.data}'")
        await query.answer()

        action = query.data.replace('quick_', '')
        message = query.message  # Используем message из callback напрямую

        try:
            if action == 'stats':
                await self._handle_stats(update.effective_user.id, message)
            elif action == 'plan':
                await self._handle_plan(update.effective_user.id, message)
            elif action == 'sync':
                await self._handle_sync(update.effective_user.id, message, context)
            elif action == 'calendar':
                await self._handle_calendar(update.effective_user.id, message)
            logger.info(f"✅ Quick action '{action}' выполнен для user={update.effective_user.id}")
        except Exception as e:
            logger.error(f"❌ ОШИБКА в quick action '{action}': {e}")
            import traceback
            logger.error(traceback.format_exc())
            await message.reply_text(f"❌ Ошибка: {e}")

    async def debug_callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Debug: ловит все неперехваченные callbacks"""
        query = update.callback_query
        logger.warning(f"⚠️ НЕПЕРЕХВАЧЕННЫЙ CALLBACK: user={update.effective_user.id}, data='{query.data}'")
        await query.answer("Debug: этот callback не обработан")

    async def handle_ai_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений через AI-агента или онбординг"""
        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)
        message_text = update.message.text.strip()

        # === ОНБОРДИНГ: ввод кастомной дистанции (шоссе) ===
        if context.user_data.get('awaiting_custom_distance'):
            logger.info(f"Обработка кастомной дистанции от user={telegram_id}: '{message_text}'")
            try:
                distance_km = int(message_text)
                if distance_km < 1 or distance_km > 500:
                    raise ValueError(f"Дистанция вне диапазона: {distance_km}")

                db.save_user_goal(user.id, goal_type='race', goal_distance_km=distance_km)
                context.user_data['awaiting_custom_distance'] = False
                logger.info(f"Сохранена кастомная дистанция {distance_km} км для user={telegram_id}")

                await update.message.reply_text(f"🏁 Готовимся к {distance_km} км!")
                await self._ask_goal_date(message=update.message, context=context)
                return
            except ValueError as e:
                logger.warning(f"Некорректная дистанция от user={telegram_id}: {e}")
                await update.message.reply_text("❌ Пожалуйста, введи число\n(например: 10, 21, 42)")
                return

        # === ОНБОРДИНГ: ввод дистанции трейла ===
        if context.user_data.get('awaiting_trail_distance'):
            logger.info(f"Обработка дистанции трейла от user={telegram_id}: '{message_text}'")
            try:
                distance_km = int(message_text)
                if distance_km < 1 or distance_km > 500:
                    raise ValueError(f"Дистанция вне диапазона: {distance_km}")

                db.save_user_goal(user.id, goal_distance_km=distance_km, goal_type="trail")
                context.user_data['awaiting_trail_distance'] = False
                logger.info(f"Сохранена дистанция трейла {distance_km} км для user={telegram_id}")

                # Спрашиваем набор высоты
                await update.message.reply_text(
                    f"✅ Дистанция: {distance_km} км\n\n"
                    "⛰️ Какой набор высоты в метрах?\n"
                    "(например: 1000, 2500, 5000):"
                )
                context.user_data['awaiting_trail_elevation'] = True
                return
            except ValueError as e:
                logger.warning(f"Некорректная дистанция трейла от user={telegram_id}: {e}")
                await update.message.reply_text("❌ Пожалуйста, введи число\n(например: 30, 50, 100)")
                return

        # === ОНБОРДИНГ: ввод набора высоты для трейла ===
        if context.user_data.get('awaiting_trail_elevation'):
            logger.info(f"Обработка набора высоты от user={telegram_id}: '{message_text}'")
            try:
                elevation_gain = int(message_text)
                if elevation_gain < 0 or elevation_gain > 15000:
                    raise ValueError(f"Набор высоты вне диапазона: {elevation_gain}")

                db.save_user_goal(user.id, goal_elevation_gain=elevation_gain)
                context.user_data['awaiting_trail_elevation'] = False
                logger.info(f"Сохранён набор высоты {elevation_gain}м для user={telegram_id}")

                # Спрашиваем количество пунктов питания
                await update.message.reply_text(
                    f"✅ Набор высоты: {elevation_gain} м\n\n"
                    "🚰 Сколько пунктов питания на трассе?\n"
                    "(например: 3, 5, 10):"
                )
                context.user_data['awaiting_trail_aid_stations'] = True
                return
            except ValueError as e:
                logger.warning(f"Некорректный набор высоты от user={telegram_id}: {e}")
                await update.message.reply_text("❌ Пожалуйста, введи число\n(например: 1000, 2500, 5000)")
                return

        # === ОНБОРДИНГ: ввод количества пунктов питания для трейла ===
        if context.user_data.get('awaiting_trail_aid_stations'):
            logger.info(f"Обработка пунктов питания от user={telegram_id}: '{message_text}'")
            try:
                aid_stations = int(message_text)
                if aid_stations < 0 or aid_stations > 50:
                    raise ValueError(f"Количество пунктов вне диапазона: {aid_stations}")

                db.save_user_goal(user.id, goal_aid_stations=aid_stations)
                context.user_data['awaiting_trail_aid_stations'] = False
                logger.info(f"Сохранено {aid_stations} пунктов питания для user={telegram_id}")

                await update.message.reply_text(f"✅ Пунктов питания: {aid_stations}")
                await self._ask_goal_date(message=update.message, context=context)
                return
            except ValueError as e:
                logger.warning(f"Некорректное количество пунктов от user={telegram_id}: {e}")
                await update.message.reply_text("❌ Пожалуйста, введи число\n(например: 3, 5, 10)")
                return

        # === ОНБОРДИНГ: ввод даты забега ===
        if context.user_data.get('awaiting_goal_date'):
            logger.info(f"Обработка даты забега от user={telegram_id}: '{message_text}'")
            from datetime import datetime

            try:
                # Парсим дату в формате ДД.ММ.ГГГГ
                goal_date = datetime.strptime(message_text, "%d.%m.%Y").date()

                # Проверяем что дата в будущем
                if goal_date <= time_utils.today():
                    await update.message.reply_text(
                        "❌ Дата должна быть в будущем!\n\n"
                        "Введи дату забега в формате ДД.ММ.ГГГГ\n"
                        "(например: 15.05.2026):"
                    )
                    return

                # Сохраняем дату
                goal_type = context.user_data.get('goal_type', 'race')
                db.save_user_goal(user.id, goal_type=goal_type, goal_date=goal_date)
                context.user_data['awaiting_goal_date'] = False
                logger.info(f"Сохранена дата забега {goal_date} для user={telegram_id}")

                await update.message.reply_text(f"✅ Отлично! Цель: {goal_date.strftime('%d.%m.%Y')}")
                await self._show_days_selection(message=update.message, context=context)
                return

            except ValueError as e:
                logger.warning(f"Некорректная дата от user={telegram_id}: {e}")
                await update.message.reply_text(
                    "❌ Неправильный формат даты!\n\n"
                    "Введи дату в формате ДД.ММ.ГГГГ\n"
                    "(например: 15.05.2026 или 01.09.2026):"
                )
                return

        # === ОНБОРДИНГ: ввод времени тренировок ===
        if context.user_data.get('awaiting_time'):
            # Парсим введённое время
            import re
            time_min = None
            text_lower = message_text.lower().strip()

            try:
                # 1. Простое число: "90"
                time_min = int(message_text)
            except ValueError:
                # 2. С единицами: "90 минут", "90 мин", "1.5 часа", "2 ч"
                patterns_units = [
                    (r'(\d+(?:\.\d+)?)\s*(?:час|hour|h|ч)', lambda m: int(float(m.group(1)) * 60)),  # часы
                    (r'(\d+)\s*(?:минут|мин|min|м)', lambda m: int(m.group(1))),  # минуты
                ]

                for pattern, converter in patterns_units:
                    match = re.search(pattern, text_lower)
                    if match:
                        time_min = converter(match)
                        break

                # 3. Диапазон времени: "с 19 до 21", "19-21", "19:10-20:40"
                if time_min is None:
                    pattern = r'(?:с\s*)?(\d{1,2})(?::(\d{2}))?(?:\s*до\s*|\s*-\s*)(\d{1,2})(?::(\d{2}))?'
                    match = re.search(pattern, text_lower)

                    if match:
                        start_hour = int(match.group(1))
                        start_min = int(match.group(2)) if match.group(2) else 0
                        end_hour = int(match.group(3))
                        end_min = int(match.group(4)) if match.group(4) else 0

                        # Переводим в минуты от начала дня
                        start_total = start_hour * 60 + start_min
                        end_total = end_hour * 60 + end_min

                        # Вычисляем разницу
                        if end_total > start_total:
                            time_min = end_total - start_total
                        else:
                            # Через полночь (например, с 22:00 до 02:00)
                            time_min = (24 * 60 - start_total) + end_total

                        # Формируем красивый вывод
                        hours = time_min // 60
                        mins = time_min % 60
                        if mins > 0:
                            time_str = f"{hours} ч {mins} мин" if hours > 0 else f"{mins} мин"
                        else:
                            time_str = f"{hours} ч"

                        await update.message.reply_text(f"✅ Понял: {time_str} = {time_min} мин")

            if time_min is None or time_min < 30 or time_min > 300:
                await update.message.reply_text(
                    "❌ Не могу распознать время или значение вне допустимого диапазона (30-300 мин)\n\n"
                    "Напиши:\n"
                    "• Просто число минут: 60, 90, 120\n"
                    "• Или диапазон: с 19 до 21\n"
                    "• Или с минутами: с 19:10 до 20:40"
                )
                return

            # Сохраняем время в минутах
            goal_type = context.user_data.get('goal_type', 'fitness')
            db.save_user_goal(user.id, goal_type=goal_type, training_time_min=time_min)
            context.user_data['awaiting_time'] = False
            context.user_data['time_per_session'] = time_min

            logger.info(f"Время тренировки для user={user.id}: {time_min} мин")

            # Спрашиваем время старта в будни (текстовый ввод)
            context.user_data['awaiting_start_time_weekday'] = True
            await update.message.reply_text(
                "🕐 Во сколько обычно бегаешь в **будни**?\n\n"
                "Напиши время старта (например: 19:00, 7:30, 6)",
                parse_mode='Markdown'
            )
            return

        # === ОНБОРДИНГ: ввод времени старта (будни) ===
        if context.user_data.get('awaiting_start_time_weekday'):
            import re
            # Парсим время: "19:00", "7:30", "6" → "19:00", "07:30", "06:00"
            time_str = None
            match = re.search(r'(\d{1,2})(?::(\d{2}))?', message_text.strip())
            if match:
                hour = int(match.group(1))
                minute = int(match.group(2)) if match.group(2) else 0
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    time_str = f"{hour:02d}:{minute:02d}"

            if not time_str:
                await update.message.reply_text(
                    "❌ Не могу распознать время\n\n"
                    "Напиши в формате: 19:00 или 7:30 или просто 6"
                )
                return

            # Сохраняем время для будней
            db.save_user_goal(user.id, start_time_weekday=time_str)
            context.user_data['start_time_weekday'] = time_str
            context.user_data['awaiting_start_time_weekday'] = False

            # Спрашиваем время для выходных
            context.user_data['awaiting_start_time_weekend'] = True
            await update.message.reply_text(
                f"✅ Будни: {time_str}\n\n"
                "🕐 А во сколько бегаешь в **выходные**?\n\n"
                "Напиши время старта (например: 9:00, 10, 8:30)",
                parse_mode='Markdown'
            )
            return

        # === ОНБОРДИНГ: ввод времени старта (выходные) ===
        if context.user_data.get('awaiting_start_time_weekend'):
            import re
            time_str = None
            match = re.search(r'(\d{1,2})(?::(\d{2}))?', message_text.strip())
            if match:
                hour = int(match.group(1))
                minute = int(match.group(2)) if match.group(2) else 0
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    time_str = f"{hour:02d}:{minute:02d}"

            if not time_str:
                await update.message.reply_text(
                    "❌ Не могу распознать время\n\n"
                    "Напиши в формате: 9:00 или 10 или 8:30"
                )
                return

            # Сохраняем время для выходных
            db.save_user_goal(user.id, start_time_weekend=time_str)
            context.user_data['start_time_weekend'] = time_str
            context.user_data['awaiting_start_time_weekend'] = False

            # Завершаем онбординг
            await self._finish_onboarding(user.id, context, update.message)
            return

        logger.info(f"💬 AI-чат от user={telegram_id}: {message_text[:50]}...")

        # Проверяем что пользователь зарегистрирован
        credentials = db.get_user_garmin_credentials(user.id)
        strava_creds = db.get_user_strava_credentials(user.id)

        if not credentials and not strava_creds:
            await update.message.reply_text(
                "Сначала подключи Garmin или Strava через /start"
            )
            return

        # Показываем что печатаем
        await context.bot.send_chat_action(chat_id=telegram_id, action="typing")

        try:
            from ..integrations.ai_agent import ai_agent

            response = await ai_agent.chat(user.id, message_text)

            await update.message.reply_text(
                response,
                parse_mode='Markdown'
            )

            logger.info(f"✅ AI ответил user={telegram_id}")

        except Exception as e:
            logger.error(f"Ошибка AI-чата: {e}")
            await update.message.reply_text(
                "Произошла ошибка. Попробуй позже или используй команды (/help)"
            )

    async def ask_plan_days(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало создания плана - выбор дней недели"""
        from datetime import date

        query = update.callback_query
        await query.answer()

        # Определяем цель
        goal_mapping = {
            'plan_tarki': {'name': 'Тарки-Тау 50км', 'distance': 50, 'date': date(2026, 2, 15), 'type': 'trail'},
            'plan_marathon': {'name': 'Марафон 42км', 'distance': 42, 'date': date(2026, 3, 15), 'type': 'race'},
            'plan_dwt': {'name': 'DWT 65км', 'distance': 65, 'date': date(2026, 4, 15), 'type': 'trail'}
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

        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        # Парсим введённое время
        text = update.message.text.strip().lower()
        time_min = None

        try:
            # Пробуем распарсить как простое число
            time_min = int(text)
        except ValueError:
            # Пробуем распарсить "с X до Y" или "с X:MM до Y:MM"
            import re

            # Паттерны: "с 19 до 21", "19-21", "с 19:10 до 20:40", "19:30-21:00"
            pattern = r'(?:с\s*)?(\d{1,2})(?::(\d{2}))?(?:\s*до\s*|\s*-\s*)(\d{1,2})(?::(\d{2}))?'
            match = re.search(pattern, text)

            if match:
                start_hour = int(match.group(1))
                start_min = int(match.group(2)) if match.group(2) else 0
                end_hour = int(match.group(3))
                end_min = int(match.group(4)) if match.group(4) else 0

                # Переводим в минуты от начала дня
                start_total = start_hour * 60 + start_min
                end_total = end_hour * 60 + end_min

                # Вычисляем разницу
                if end_total > start_total:
                    time_min = end_total - start_total
                else:
                    # Через полночь (например, с 22:00 до 02:00)
                    time_min = (24 * 60 - start_total) + end_total

                # Формируем красивый вывод
                hours = time_min // 60
                mins = time_min % 60
                if mins > 0:
                    time_str = f"{hours} ч {mins} мин" if hours > 0 else f"{mins} мин"
                else:
                    time_str = f"{hours} ч"

                await update.message.reply_text(
                    f"✅ Понял: {time_str} = {time_min} мин"
                )

        if time_min is None:
            await update.message.reply_text(
                "❌ Не могу распознать время\n\n"
                "Напиши:\n"
                "• Просто число минут: 60, 90, 120\n"
                "• Или диапазон: с 19 до 21\n\n"
                "Или отправь /cancel для отмены"
            )
            return PLAN_TIME

        if time_min < 30 or time_min > 300:
            await update.message.reply_text(
                "❌ Время должно быть от 30 до 300 минут (0.5-5 часов)\n\n"
                "Попробуй ещё раз или отправь /cancel"
            )
            return PLAN_TIME

        # Сохраняем время и спрашиваем про уровень подготовки
        context.user_data['time_per_session'] = time_min

        from telegram import InlineKeyboardButton
        from telegram import InlineKeyboardMarkup

        keyboard = [
            [InlineKeyboardButton("🟢 Новичок (бегаю < 6 месяцев)", callback_data="level_beginner")],
            [InlineKeyboardButton("🟡 Средний (6-24 месяца)", callback_data="level_intermediate")],
            [InlineKeyboardButton("🔴 Опытный (бегаю > 2 лет)", callback_data="level_advanced")]
        ]

        await update.message.reply_text(
            "🏃 Какой у тебя опыт в беге?\n\n"
            "Это нужно чтобы адаптировать объём и интенсивность тренировок",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        context.user_data['awaiting_level'] = True
        return PLAN_TIME

    async def handle_start_time_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора времени старта тренировок (будни/выходные)"""
        query = update.callback_query
        await query.answer()

        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        # Парсим callback: starttime_wd_07:00 или starttime_we_09:00
        data = query.data.replace("starttime_", "")
        day_type, time_value = data.split("_", 1)

        if day_type == "wd":
            # Сохранили время для будней, теперь спрашиваем выходные
            db.save_user_goal(user.id, start_time_weekday=time_value)
            context.user_data['start_time_weekday'] = time_value

            keyboard = [
                [
                    InlineKeyboardButton("07:00", callback_data="starttime_we_07:00"),
                    InlineKeyboardButton("08:00", callback_data="starttime_we_08:00"),
                    InlineKeyboardButton("09:00", callback_data="starttime_we_09:00"),
                ],
                [
                    InlineKeyboardButton("10:00", callback_data="starttime_we_10:00"),
                    InlineKeyboardButton("11:00", callback_data="starttime_we_11:00"),
                    InlineKeyboardButton("12:00", callback_data="starttime_we_12:00"),
                ]
            ]
            await query.message.edit_text(
                f"✅ Будни: {time_value}\n\n"
                "🕐 А в **выходные** во сколько бегаешь?\n\n"
                "Выбери примерное время старта:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            # day_type == "we" — сохранили время для выходных, завершаем онбординг
            db.save_user_goal(user.id, start_time_weekend=time_value)
            context.user_data['start_time_weekend'] = time_value

            weekday_time = context.user_data.get('start_time_weekday', '07:00')

            await query.message.edit_text(
                f"✅ Время старта сохранено:\n"
                f"• Будни: {weekday_time}\n"
                f"• Выходные: {time_value}\n\n"
                "⏳ Завершаю настройку..."
            )

            # Продолжаем с созданием плана
            await self._finish_onboarding(user.id, context, query.message)

    async def _finish_onboarding(self, user_id: int, context: ContextTypes.DEFAULT_TYPE, message):
        """Завершение онбординга: напоминания и создание плана"""
        # Настраиваем напоминания
        reminder_scheduler = get_reminder_scheduler()
        if reminder_scheduler:
            reminder_scheduler.schedule_user_reminders(user_id)
            logger.info(f"🔔 Напоминания настроены для user={user_id}")

        # Автосоздание плана для забегов
        goal_type = context.user_data.get('goal_type', 'fitness')
        plan_created = False

        if goal_type in ['race', 'trail']:
            logger.info(f"Автосоздание плана для забега user={user_id}")
            plan_created = await self._auto_create_race_plan(user_id, message)

        if plan_created:
            await message.reply_text(
                "🎉 Настройка завершена!\n\n"
                "✅ План тренировок создан и готов к использованию\n\n"
                "Теперь бот будет:\n"
                "• Показывать план на неделю (/plan)\n"
                "• Напоминать о тренировках\n"
                "• Спрашивать самочувствие после тренировок\n\n"
                "Или просто напиши мне — я помогу скорректировать тренировки!"
            )
        else:
            await message.reply_text(
                "🎉 Отлично, всё настроено!\n\n"
                "Теперь бот будет:\n"
                "• Показывать план на неделю (/plan)\n"
                "• Напоминать о тренировках\n"
                "• Спрашивать самочувствие после тренировок\n\n"
                "Или просто напиши мне — я помогу скорректировать тренировки!"
            )

        logger.info(f"Онбординг завершён для user={user_id}")

    async def handle_level_onboarding(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора уровня подготовки в онбординге"""
        query = update.callback_query
        await query.answer()

        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        # Извлекаем уровень из callback_data: level_onboarding_beginner → beginner
        level = query.data.replace("level_onboarding_", "")

        # Сохраняем уровень в БД
        db.save_user_goal(user.id, fitness_level=level)

        # Сохраняем уровень в context для использования в текущей сессии
        context.user_data['fitness_level'] = level

        logger.info(f"User {telegram_id} выбрал уровень подготовки: {level}")

        # Спрашиваем время на тренировку
        await query.message.reply_text(
            "⏱ Сколько времени у тебя на одну тренировку?\n\n"
            "Напиши в минутах (например: 60, 90, 120)\n"
            "Или диапазон времени (например: с 19 до 21)"
        )
        context.user_data['awaiting_time'] = True

    async def handle_level_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора уровня подготовки и генерация плана"""
        from ..core.plan_generator import PlanGenerator

        query = update.callback_query
        await query.answer()

        # Извлекаем уровень
        level = query.data.replace("level_", "")  # beginner/intermediate/advanced

        # Получаем сохранённые данные
        goal_data = context.user_data.get('goal_data')
        selected_days = context.user_data.get('selected_days', [])
        time_min = context.user_data.get('time_per_session', 60)

        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        await query.message.edit_text(
            f"⏳ Генерирую индивидуальный план...\n\n"
            f"🎯 Цель: {goal_data['name']}\n"
            f"📅 Дней в неделю: {len(selected_days)}\n"
            f"⏱ Время на тренировку: {time_min} мин\n"
            f"🏃 Уровень: {level}"
        )

        # Генерируем план с учетом уровня
        generator = PlanGenerator(user.id)

        trainings = generator.generate_detailed_plan(
            goal_distance=goal_data['distance'],
            goal_date=goal_data['date'],
            training_days=selected_days,
            time_per_session=time_min,
            weeks=4,
            goal_type=goal_data.get('type', 'race'),
            fitness_level=level
        )

        # Сохраняем в БД
        count = generator.save_plan_to_db(trainings)

        await query.message.reply_text(
            f"✅ План создан!\n\n"
            f"🎯 Цель: {goal_data['name']} ({goal_data['date'].strftime('%d.%m.%Y')})\n"
            f"📅 Сгенерировано тренировок: {count}\n"
            f"📆 Период: 4 недели\n\n"
            "Используй /plan чтобы посмотреть план на неделю"
        )

        # Показываем методологию персонализации
        methodology = generator.get_methodology_summary()
        await query.message.reply_text(methodology, parse_mode='Markdown')

        logger.info(f"Пользователь {telegram_id} создал индивидуальный план для {goal_data['name']} (уровень: {level})")
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
            BotCommand("records", "Персональные рекорды"),
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
                # Инициализируем планировщик напоминаний
                self.reminder_scheduler = init_reminder_scheduler(self.send_notification_message)
                logger.info("✅ Планировщик напоминаний инициализирован")

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

        # Останавливаем планировщик напоминаний
        if self.reminder_scheduler:
            self.reminder_scheduler.shutdown()

        logger.info("⏹️  Бот остановлен")
