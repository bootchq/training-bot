"""SyncMixin — Синхронизация с Garmin и утилиты"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ...core.stats_calculator import StatsCalculator
from ...core.vdot_calculator import calculate_best_vdot, format_vdot_summary, get_training_paces
from ...database.db import db
from ...ai.recovery_detector import recovery_detector
from ...integrations.calendar_sync import calendar_sync
from ...integrations.garmin_sync import garmin_sync
from ...utils import time_utils
from ...utils.logger import logger


class SyncMixin:
    """Синхронизация с Garmin и утилиты"""

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

    def _get_daily_recommendation(self, user_id: int) -> str:
        """
        Получить рекомендацию на сегодня с учётом AI recovery status

        Returns:
            Текст рекомендации или пустая строка
        """
        from datetime import timedelta

        today = time_utils.today()

        # Получаем план на сегодня
        today_plan = db.get_plan_for_date(user_id, today)
        if not today_plan:
            return ""

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

        # AI Recovery Detection
        try:
            recovery = recovery_detector.detect_recovery_status(user_id)
            status = recovery['status']

            if status == 'rest':
                recommendation += "\n🔴 Восстановление: рекомендован отдых"
                recommendation += f"\n   {recovery['reasoning']}"
            elif status == 'easy':
                recommendation += "\n🟡 Восстановление: только лёгкая тренировка"
                if today_plan.type in ['intervals', 'tempo', 'long']:
                    recommendation += "\n   ⚠️ Снизь интенсивность!"
            elif status == 'hard':
                recommendation += "\n🟢 Восстановление: отличное, можно интенсив"
        except Exception as e:
            logger.debug(f"Recovery detection недоступен: {e}")
            # Fallback на старую логику
            wellness = db.get_latest_wellness(user_id)
            if wellness and wellness.date >= today - timedelta(days=2):
                warnings = []
                if wellness.sleep_quality in ('bad', '1', '2'):
                    warnings.append("плохой сон")
                if wellness.wellness_rating and wellness.wellness_rating <= 2:
                    warnings.append("усталость")
                if wellness.pain_reported:
                    warnings.append("боль")
                if warnings:
                    recommendation += f"\n⚠️ Учтено: {', '.join(warnings)}"

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
            # Используем generic цели вместо hard-coded
            keyboard = [
                [InlineKeyboardButton("🏃 Полумарафон 21км", callback_data="plan_half")],
                [InlineKeyboardButton("🏃 Марафон 42км", callback_data="plan_marathon")],
                [InlineKeyboardButton("⛰ Трейл 50км", callback_data="plan_trail50")]
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
            plan_text = f"**{day_name} {plan.date.strftime('%d.%m')}**\n"

            # Добавляем цель тренировки
            if hasattr(plan, 'goal') and plan.goal:
                plan_text += f"🎯 {plan.goal}\n\n"
            else:
                plan_text += "\n"

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

            await message.reply_text(plan_text, parse_mode='Markdown')

        logger.info(f"Пользователь {telegram_id} запросил план")

    async def _handle_sync(self, telegram_id: int, message, context):
        """Внутренняя логика синхронизации — делегирует в _sync_with_status"""
        await self._sync_with_status(telegram_id, message, context, is_registration=False)

    async def _sync_with_status(self, telegram_id: int, message, context, is_registration: bool = False):
        """
        Единый метод синхронизации с Garmin.
        UX: сообщение "Подожди 2-5 минут" → редактирование на результат.
        Полная синхронизация: 60 дней + VDOT + LTHR.
        """
        from ...core.vdot_calculator import calculate_best_vdot, format_vdot_summary, get_training_paces

        user = db.get_or_create_user(telegram_id)
        credentials = db.get_user_garmin_credentials(user.id)

        if not credentials:
            await message.reply_text(
                "❌ Учетные данные Garmin не найдены.\n\n"
                "Используй /start для регистрации"
            )
            return

        # Получаем текущий VDOT для сравнения
        old_settings = db.get_user_settings(user.id)
        old_vdot = old_settings.get('vdot') if old_settings else None

        # Отправляем сообщение и сохраняем для редактирования
        if is_registration:
            status_message = await message.reply_text(
                "✅ Регистрация завершена!\n\n"
                "Синхронизирую твои тренировки...\n"
                "Подожди 2-5 минут ⏳"
            )
        else:
            status_message = await message.reply_text(
                "📥 Синхронизирую тренировки за последние 60 дней...\n"
                "Подожди 2-5 минут ⏳"
            )

        try:
            # Авторизуемся в Garmin
            email, password = credentials
            if not garmin_sync.login(email, password):
                await status_message.edit_text(
                    "❌ Не удалось авторизоваться в Garmin.\n\n"
                    "Проверь правильность логина/пароля"
                )
                return

            # Полная синхронизация: 60 дней + LTHR + Personal Records
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

            # Формируем результат
            result_lines = []
            if total_count > 0:
                result_lines.append(f"✅ Загружено {total_count} тренировок за 60 дней")
            else:
                result_lines.append("ℹ️ Новых тренировок не найдено")

            # Физиологические данные
            if lthr or vdot:
                result_lines.append("\n**Физиологические данные:**")
                if lthr:
                    # Показываем max HR для контекста (чтобы понять откуда LTHR)
                    recent_trainings = db.get_user_trainings(user.id, limit=60)
                    max_hrs = [t.max_hr for t in recent_trainings if t.max_hr and t.max_hr > 100]
                    if max_hrs:
                        max_hr = max(max_hrs)
                        result_lines.append(f"- LTHR: {lthr} уд/мин (макс. пульс: {max_hr} уд/мин)")
                    else:
                        result_lines.append(f"- LTHR: {lthr} уд/мин")

            # Проверяем рост VDOT
            vdot_changed = False
            if vdot:
                if old_vdot and vdot > old_vdot:
                    delta = vdot - old_vdot
                    result_lines.append(f"- VDOT: {vdot:.0f} (было {old_vdot:.0f}, **+{delta:.1f}**)")
                    vdot_changed = True
                else:
                    result_lines.append(f"- VDOT: {vdot:.0f} (по {vdot_source})")

            # При регистрации/онбординге — определяем уровень и показываем кнопки
            if is_registration:
                from ...core.fitness_detector import detect_fitness_level, format_level_with_evidence

                detected_level, level_stats = detect_fitness_level(user.id)
                if detected_level:
                    db.save_user_goal(user.id, fitness_level=detected_level)
                    context.user_data['fitness_level'] = detected_level

                    # Добавляем анализ уровня (уровень указан внутри)
                    level_evidence = format_level_with_evidence(user.id, detected_level, level_stats)
                    result_lines.append(f"\n{level_evidence}")

                result_lines.append("\n▶️ Настроим план тренировок")

                keyboard = [
                    [
                        InlineKeyboardButton("📅 Календарь", callback_data="setup_google_calendar"),
                        InlineKeyboardButton("⏭ Настройка", callback_data="start_onboarding")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await status_message.edit_text(
                    "\n".join(result_lines),
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            else:
                # Обычная синхронизация — просто результат
                await status_message.edit_text("\n".join(result_lines), parse_mode='Markdown')

                # Если VDOT вырос — показываем обновлённые темпы
                if vdot_changed:
                    paces = get_training_paces(vdot)
                    if paces:
                        pace_text = "🚀 **Темпы пересчитаны!**\n\n"
                        pace_text += f"• Easy: {paces.get('E', 'N/A')}\n"
                        pace_text += f"• Threshold: {paces.get('T', 'N/A')}\n"
                        pace_text += f"• Interval: {paces.get('I', 'N/A')}\n"
                        pace_text += "\nНовые темпы применяются к будущим тренировкам"
                        await message.reply_text(pace_text, parse_mode='Markdown')

            # Показываем VDOT summary если есть
            if vdot and vdot_source and vdot_time:
                summary = format_vdot_summary(vdot, vdot_source, vdot_time)
                await message.reply_text(summary, parse_mode='Markdown')

            return total_count  # Возвращаем для AI-анализа в /sync

        except Exception as e:
            logger.error(f"Ошибка синхронизации для {telegram_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            await status_message.edit_text(
                "❌ Ошибка синхронизации с Garmin.\n\n"
                "Проверь правильность логина/пароля"
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
