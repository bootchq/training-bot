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
from ..core.wellness_survey import WellnessSurvey
from ..database.db import db
from ..ai.workout_recommender import workout_recommender
from ..ai.recovery_detector import recovery_detector
from ..ai.weekly_coach import weekly_coach
from ..ai.smart_advisor import smart_advisor
from ..integrations.calendar_sync import calendar_sync
from ..utils import time_utils
from ..utils.config import Config
from ..utils.logger import logger
from .handlers import AIChatMixin, OnboardingMixin, SyncMixin

# Состояния для ConversationHandler
GARMIN_EMAIL, GARMIN_PASSWORD = range(2)
PLAN_DAYS, PLAN_TIME = range(2, 4)


class TrainingBot(OnboardingMixin, AIChatMixin, SyncMixin):
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
        self.app.add_handler(CommandHandler("state", self.state_command))
        self.app.add_handler(CommandHandler("records", self.records))
        self.app.add_handler(CommandHandler("plan", self.plan))
        self.app.add_handler(CommandHandler("calendar", self.calendar))
        self.app.add_handler(CommandHandler("skip", self.skip_training))
        self.app.add_handler(CommandHandler("set_google_token", self.set_google_token))
        self.app.add_handler(CommandHandler("reset", self.reset_user))
        self.app.add_handler(CommandHandler("zones", self.zones_command))
        self.app.add_handler(CommandHandler("methodology", self.methodology_command))
        self.app.add_handler(CommandHandler("admin", self.admin_command))
        self.app.add_handler(CommandHandler("ai_suggest", self.ai_suggest_command))
        self.app.add_handler(CommandHandler("weekly", self.weekly_command))
        self.app.add_handler(CommandHandler("recovery", self.recovery_command))
        self.app.add_handler(CommandHandler("next", self.next_workout))

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

        # ConversationHandlers после standalone handlers
        self.app.add_handler(garmin_registration_handler)
        self.app.add_handler(plan_creation_handler)
        # Debug: catch-all handler для неперехваченных callbacks
        self.app.add_handler(CallbackQueryHandler(self.debug_callback_handler))
        # AI-чат: обработка текстовых сообщений (после всех команд и ConversationHandlers)
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_ai_chat))
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

📬 Обратная связь: @bootchq
"""
            await update.message.reply_text(welcome_text, reply_markup=reply_markup)
            logger.info(f"Новый пользователь {telegram_id}, запрос регистрации Garmin")
            return

        # Есть credentials → ВСЕГДА синхронизация (железное правило)
        # Определяем: после синхронизации показать онбординг или меню
        is_onboarding_needed = not user.onboarding_completed

        # Синхронизация с правильным UX
        await self._sync_with_status(
            telegram_id,
            update.message,
            context,
            is_registration=is_onboarding_needed  # Если нужен онбординг — покажет кнопки
        )

        # Если онбординг уже завершён — показываем меню после синхронизации
        if not is_onboarding_needed:
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
📬 Обратная связь: @bootchq
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
/next — Лучшая тренировка на сегодня (умный анализ)
/sync — Синхронизация с Garmin (вручную)
/plan — План тренировок на текущую неделю
/state — Текущее состояние (анализ за 4 недели)
/stats — Статистика за неделю
/stats month — Статистика за месяц
/calendar — Скачать план в ICS для календаря
/zones — Персональные зоны пульса
/methodology — Методология расчёта темпов

✅ Реализовано:
• Автоматическая синхронизация Garmin
• Персонализация по VDOT и LTHR
• Адаптивный план тренировок
• Предсказывающая адаптация (Safety First)
• Вечерний опрос самочувствия
• Экспорт плана в календарь

📬 Обратная связь: @bootchq
"""
        await update.message.reply_text(help_text)

    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin — статистика для админа"""
        telegram_id = update.effective_user.id

        # Проверка доступа
        if telegram_id != Config.ADMIN_TELEGRAM_ID:
            await update.message.reply_text("⛔ Доступ запрещён")
            return

        # Получаем статистику
        stats = db.get_admin_stats()

        admin_text = f"""
📊 Админ-панель

👥 Всего пользователей: {stats['total_users']}
✅ Завершили онбординг: {stats['onboarded_users']}
🔗 С Garmin credentials: {stats['users_with_garmin']}
🏃 Активных за неделю: {stats['active_last_week']}
"""
        await update.message.reply_text(admin_text)
        logger.info(f"Admin {telegram_id} запросил статистику")

    async def state_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /state - показать текущее состояние бегуна за 4 недели"""
        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        try:
            # Создаем адаптер и получаем состояние
            adapter = PlanAdapter(user.id)
            state = adapter.get_runner_state()

            # Получаем простой статус для beginner
            simple = state.get_simple_status()

            # Форматируем сообщение
            message = f"{simple['icon']} *{simple['message']}*\n\n"
            message += f"_{simple['detail']}_\n\n"
            message += "━━━━━━━━━━━━━━━━━━━━\n\n"

            # Краткая сводка за 4 недели
            message += f"📊 *Анализ за 4 недели:*\n\n"
            message += f"📈 Объём: {state.volume.avg_weekly_km:.1f} км/неделя\n"
            message += f"⚡ Интенсив: {state.intensity.intense_minutes_week} мин/неделя ({state.intensity.actual_ratio*100:.0f}%)\n"

            # Easy HR тренд (если есть)
            if state.response.easy_hr_baseline and state.response.easy_hr_current:
                hr_trend_icon = "🟢" if state.response.easy_hr_trend == "stable" else "🔴"
                message += f"{hr_trend_icon} Easy HR: {state.response.easy_hr_current} bpm"
                if state.response.easy_hr_delta_pct:
                    delta_sign = "+" if state.response.easy_hr_delta_pct > 0 else ""
                    message += f" ({delta_sign}{state.response.easy_hr_delta_pct:.1f}%)"
                message += "\n"

            # Wellness (если есть)
            if state.response.wellness_avg:
                message += f"💪 Самочувствие: {state.response.wellness_avg:.1f}/10\n"

            message += "\n"
            message += f"💡 *Рекомендация:*\n_{state.recommendation.reason}_"

            await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Ошибка получения runner_state: {e}", exc_info=True)
            await update.message.reply_text(
                "Не удалось получить состояние.\n\n"
                "Возможно, недостаточно данных за последние 4 недели.\n"
                "Используй /sync для синхронизации тренировок."
            )

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

        # Единый метод синхронизации (UX: "Подожди 2-5 минут" → редактирование)
        total_count = await self._sync_with_status(telegram_id, update.message, context, is_registration=False)

        # AI-анализ последней тренировки (только если были загружены тренировки)
        if total_count and total_count > 0:
            latest_training = db.get_latest_training(user.id)
            if latest_training:
                await update.message.reply_text("🤖 Анализирую последнюю тренировку...")

                user_goal = db.get_user_settings(user.id)
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
                    records_text += "\nПоздравляю! Продолжай в том же духе!"
                    await update.message.reply_text(records_text)

    async def ai_suggest_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /ai_suggest - AI рекомендация тренировки"""
        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        await update.message.reply_text("🤖 Анализирую данные...")

        try:
            rec = workout_recommender.get_recommendation(user.id)

            text = f"🏃 **AI рекомендация тренировки**\n\n"
            text += f"**Тип:** {rec['workout_type']}\n"
            text += f"**Длительность:** {rec['duration_min']} мин\n"
            text += f"**Дистанция:** {rec['distance_km']} км\n"
            text += f"**Зона пульса:** {rec['target_zone']}\n\n"
            text += f"📝 {rec['description']}\n\n"
            text += f"💡 _{rec['reasoning']}_"

            await update.message.reply_text(text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Ошибка /ai_suggest: {e}")
            await update.message.reply_text("Не удалось получить рекомендацию. Попробуй позже.")

    async def weekly_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /weekly - еженедельный AI анализ"""
        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        await update.message.reply_text("📊 Анализирую неделю...")

        try:
            insights = weekly_coach.get_weekly_insights(user.id)

            text = f"📊 **Еженедельный анализ**\n\n"
            text += f"📝 {insights['summary']}\n\n"

            pva = insights['plan_vs_actual']
            text += f"**План vs Факт:**\n"
            text += f"  Тренировок: {pva['actual_workouts']}/{pva['planned_workouts']} ({pva['completion_rate']:.0f}%)\n"
            text += f"  Дистанция: {pva['actual_distance']:.1f}/{pva['planned_distance']:.1f} км\n\n"

            if insights['insights']:
                text += "**Инсайты:**\n"
                for insight in insights['insights']:
                    text += f"  • {insight}\n"
                text += "\n"

            if insights['recommendations']:
                text += "**Рекомендации:**\n"
                for rec in insights['recommendations']:
                    text += f"  • {rec}\n"

            await update.message.reply_text(text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Ошибка /weekly: {e}")
            await update.message.reply_text("Не удалось получить анализ. Попробуй позже.")

    async def recovery_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /recovery - статус восстановления"""
        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        try:
            recovery = recovery_detector.detect_recovery_status(user.id)
            status_emoji = {'rest': '🔴', 'easy': '🟡', 'normal': '🟢', 'hard': '💪'}

            text = f"🔋 **Статус восстановления**\n\n"
            text += f"{status_emoji.get(recovery['status'], '🟢')} **{recovery['status_text']}**\n"
            text += f"Уверенность: {recovery['confidence']*100:.0f}%\n\n"
            text += f"📝 {recovery['reasoning']}\n"

            metrics = recovery.get('metrics', {})
            if metrics:
                text += "\n**Метрики:**\n"
                if metrics.get('wellness_avg'):
                    text += f"  Самочувствие: {metrics['wellness_avg']}/5\n"
                if metrics.get('sleep_avg'):
                    text += f"  Сон: {metrics['sleep_avg']}/5\n"
                if metrics.get('pain_days'):
                    text += f"  Дней с болью: {metrics['pain_days']}\n"
                if metrics.get('rhr_trend'):
                    trend_text = {'up': '↑ повышен', 'down': '↓ снижен', 'stable': '→ стабилен'}
                    text += f"  RHR: {trend_text.get(metrics['rhr_trend'], metrics['rhr_trend'])}\n"
                if metrics.get('hrv_trend'):
                    trend_text = {'up': '↑ повышен', 'down': '↓ снижен', 'stable': '→ стабилен'}
                    text += f"  HRV: {trend_text.get(metrics['hrv_trend'], metrics['hrv_trend'])}\n"

            await update.message.reply_text(text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Ошибка /recovery: {e}")
            await update.message.reply_text("Не удалось определить статус восстановления.")

    async def next_workout(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /next - умная рекомендация тренировки"""
        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)

        msg = await update.message.reply_text("🧠 Анализирую план и тренировки за 3 недели...")

        try:
            # Синхронизируем свежие данные
            try:
                await self._sync_with_status(telegram_id, update.message, context, is_registration=False)
            except Exception:
                pass  # Продолжаем даже если синхронизация не удалась

            rec = smart_advisor.get_smart_recommendation(user.id)

            # Форматируем ответ
            text = "🏃 **Рекомендация на сегодня**\n\n"
            text += f"**{rec['workout_type']}**"
            if rec.get('duration_min') and rec['duration_min'] > 0:
                text += f" | {rec['duration_min']} мин"
            if rec.get('distance_km') and rec['distance_km'] > 0:
                text += f" | ~{rec['distance_km']} км"
            if rec.get('target_zone') and rec['target_zone'] != '-':
                text += f" | {rec['target_zone']}"
            text += "\n\n"

            # Описание тренировки
            if rec.get('description'):
                text += f"{rec['description']}\n\n"

            # Почему эта тренировка
            if rec.get('reasoning'):
                text += f"💡 _{rec['reasoning']}_\n\n"

            # Контекст плана
            plan_status = rec.get('plan_status', {})
            if plan_status:
                text += "━━━━━━━━━━━━━━━━━━━━\n"
                text += f"📊 Эта неделя: {plan_status.get('done_this_week', '?')}/{plan_status.get('planned_this_week', '?')} тренировок\n"
                if plan_status.get('days_since_last_run', 0) > 0:
                    text += f"⏱ Дней без бега: {plan_status['days_since_last_run']}\n"
                skipped = plan_status.get('skipped_types', [])
                if skipped:
                    text += f"⚠️ Пропущено за 3 нед: {', '.join(skipped[:5])}\n"

            # Recovery
            recovery_status = rec.get('recovery_status', '')
            if recovery_status:
                status_emoji = {'rest': '🔴', 'easy': '🟡', 'normal': '🟢', 'hard': '💪'}
                text += f"{status_emoji.get(recovery_status, '🟢')} Recovery: {recovery_status}\n"

            await msg.edit_text(text, parse_mode='Markdown')
            logger.info(f"/next для user {telegram_id}: {rec['workout_type']}")

        except Exception as e:
            logger.error(f"Ошибка /next: {e}", exc_info=True)
            await msg.edit_text(
                "Не удалось получить рекомендацию.\n\n"
                "Попробуй /sync для обновления данных, затем /next снова."
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

            await update.message.reply_text(plan_text, parse_mode='Markdown')

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

                # AI: recovery detection + совет после wellness опроса
                try:
                    recovery = recovery_detector.detect_recovery_status(user.id)
                    status = recovery['status']
                    status_emoji = {'rest': '🔴', 'easy': '🟡', 'normal': '🟢', 'hard': '💪'}

                    recovery_msg = f"{status_emoji.get(status, '🟢')} **{recovery['status_text']}**"
                    recovery_msg += f"\n{recovery['reasoning']}"

                    await self.app.bot.send_message(
                        chat_id=telegram_id,
                        text=f"🔋 Статус восстановления:\n\n{recovery_msg}",
                        parse_mode='Markdown'
                    )
                    logger.info(f"Recovery status отправлен: {status} для user {telegram_id}")

                    # AI совет от тренера
                    yesterday = time_utils.today() - timedelta(days=1)
                    ai_advice = WellnessSurvey.get_ai_advice_for_survey(user.id, yesterday)
                    if ai_advice:
                        await self.app.bot.send_message(
                            chat_id=telegram_id,
                            text=f"🤖 Совет от AI-тренера:\n\n{ai_advice}"
                        )
                except Exception as e:
                    logger.error(f"Ошибка AI после wellness опроса: {e}")

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

        # Единый метод синхронизации (UX: "Подожди 2-5 минут" → редактирование)
        user = db.get_or_create_user(telegram_id)
        await self._sync_with_status(telegram_id, update.message, context, is_registration=True)

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

    async def register_commands(self):
        """Регистрация команд бота в BotFather"""
        from telegram import BotCommand

        commands = [
            BotCommand("start", "Начало работы"),
            BotCommand("help", "Помощь"),
            BotCommand("next", "Лучшая тренировка на сегодня"),
            BotCommand("sync", "Синхронизация с Garmin"),
            BotCommand("stats", "Статистика за неделю/месяц"),
            BotCommand("state", "Текущее состояние (анализ за 4 недели)"),
            BotCommand("records", "Персональные рекорды"),
            BotCommand("plan", "План тренировок на неделю"),
            BotCommand("zones", "Пульсовые зоны"),
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

            self.app.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True  # Избегаем конфликта при редеплое
            )
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
