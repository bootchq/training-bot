"""AI чат и обработка текстовых сообщений"""
from telegram import Update
from telegram.ext import ContextTypes

from ...database.db import db
from ...utils import time_utils
from ...utils.logger import logger


class AIChatMixin:
    """AI чат и обработка текстовых сообщений"""

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

            # Используем умный парсер дат
            goal_date = time_utils.parse_date_flexible(message_text)

            if goal_date is None:
                logger.warning(f"Не удалось распознать дату от user={telegram_id}: '{message_text}'")
                await update.message.reply_text(
                    "❌ Не удалось распознать дату.\n\n"
                    "Попробуй один из форматов:\n"
                    "• 15.03.2026\n"
                    "• 15 марта 2026\n"
                    "• 15 мар\n"
                    "• март 15"
                )
                return

            # Проверяем что дата в будущем
            if goal_date <= time_utils.today():
                await update.message.reply_text(
                    "❌ Дата должна быть в будущем!\n\n"
                    "Введи дату забега:"
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
            from ...integrations.ai_agent import ai_agent

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
