"""Обработчики онбординга и создания плана"""
from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from telegram import Update
from telegram.ext import ContextTypes
from telegram.ext import ConversationHandler

from ...core.reminders import get_reminder_scheduler
from ...database.db import db
from ...utils import time_utils
from ...utils.logger import logger

# Состояния для ConversationHandler создания плана
PLAN_DAYS, PLAN_TIME = range(2, 4)


class OnboardingMixin:
    """Обработчики онбординга и создания плана"""

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
            "Напиши дату в любом формате:\n"
            "• 15 марта 2026\n"
            "• 15.03.2026\n"
            "• март 15"
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
        from ...core.plan_generator import PlanGenerator

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

            # Проверяем есть ли уже определённый уровень (из синхронизации)
            existing_level = context.user_data.get('fitness_level')

            if existing_level:
                # Уровень уже определён при синхронизации — завершаем онбординг
                await self._finish_onboarding(user.id, context, query.message)
            else:
                # Пробуем автоопределить уровень (если синхронизация не прошла)
                from ...core.fitness_detector import detect_fitness_level

                detected_level, level_stats = detect_fitness_level(user.id)

                if detected_level:
                    db.save_user_goal(user.id, fitness_level=detected_level)
                    context.user_data['fitness_level'] = detected_level
                    # Завершаем онбординг
                    await self._finish_onboarding(user.id, context, query.message)
                else:
                    # Мало данных → спрашиваем уровень вручную
                    keyboard = [
                        [InlineKeyboardButton("🟢 Новичок в беге        ", callback_data="level_onboarding_beginner")],
                        [InlineKeyboardButton("🟡 Средний уровень       ", callback_data="level_onboarding_intermediate")],
                        [InlineKeyboardButton("🔴 Опытный бегун         ", callback_data="level_onboarding_advanced")]
                    ]

                    await query.message.reply_text(
                        "🏃 Какой у тебя опыт в беге?\n\n"
                        "Недостаточно данных в Garmin для автоматического определения.\n"
                        "Это нужно чтобы подобрать правильный объём и интенсивность.",
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

        # Завершаем онбординг (время тренировки определяется автоматически по правилам)
        await self._finish_onboarding(user.id, context, query.message)

    async def handle_level_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора уровня подготовки и генерация плана"""
        from ...core.plan_generator import PlanGenerator

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

        # Рассчитываем количество недель до забега
        days_until_race = (goal_data['date'] - time_utils.today()).days
        weeks = max(4, min(16, days_until_race // 7))

        await query.message.edit_text(
            f"⏳ Генерирую индивидуальный план...\n\n"
            f"🎯 Цель: {goal_data['name']}\n"
            f"📅 До забега: {days_until_race} дней ({weeks} недель)\n"
            f"📆 Дней в неделю: {len(selected_days)}\n"
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
            weeks=weeks,
            goal_type=goal_data.get('type', 'race'),
            fitness_level=level
        )

        # Сохраняем в БД
        count = generator.save_plan_to_db(trainings)

        await query.message.reply_text(
            f"✅ План создан!\n\n"
            f"🎯 Цель: {goal_data['name']} ({goal_data['date'].strftime('%d.%m.%Y')})\n"
            f"📅 Сгенерировано тренировок: {count}\n"
            f"📆 Период: {weeks} недель\n\n"
            "Используй /plan чтобы посмотреть план на неделю"
        )

        # Показываем методологию персонализации
        methodology = generator.get_methodology_summary()
        await query.message.reply_text(methodology, parse_mode='Markdown')

        logger.info(f"Пользователь {telegram_id} создал индивидуальный план для {goal_data['name']} (уровень: {level})")
        return ConversationHandler.END

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

    async def ask_plan_days(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало создания плана - выбор дней недели"""

        query = update.callback_query
        await query.answer()

        # Определяем цель (generic опции)
        from datetime import timedelta
        default_goal_date = time_utils.today() + timedelta(weeks=12)  # 12 недель от сегодня

        goal_mapping = {
            'plan_half': {'name': 'Полумарафон 21км', 'distance': 21, 'date': default_goal_date, 'type': 'race'},
            'plan_marathon': {'name': 'Марафон 42км', 'distance': 42, 'date': default_goal_date + timedelta(weeks=6), 'type': 'race'},
            'plan_trail50': {'name': 'Трейл 50км', 'distance': 50, 'date': default_goal_date + timedelta(weeks=4), 'type': 'trail'}
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
        import re
        text = update.message.text.strip().lower()
        time_min = None

        # Паттерн 1: "90 минут", "60 мин", "120 минут"
        min_pattern = r'^(\d+)\s*(?:минут[аы]?|мин\.?)$'
        min_match = re.match(min_pattern, text)
        if min_match:
            time_min = int(min_match.group(1))

        # Паттерн 2: "1 час", "2 часа", "1,5 часа", "1.5 часа"
        if time_min is None:
            hour_pattern = r'^(\d+(?:[.,]\d+)?)\s*(?:час[а]?|ч\.?)$'
            hour_match = re.match(hour_pattern, text)
            if hour_match:
                hours = float(hour_match.group(1).replace(',', '.'))
                time_min = int(hours * 60)

        # Паттерн 3: "1 час 30 минут", "1ч 30мин"
        if time_min is None:
            hour_min_pattern = r'^(\d+)\s*(?:час[а]?|ч\.?)\s*(\d+)\s*(?:минут[аы]?|мин\.?)$'
            hour_min_match = re.match(hour_min_pattern, text)
            if hour_min_match:
                hours = int(hour_min_match.group(1))
                mins = int(hour_min_match.group(2))
                time_min = hours * 60 + mins

        # Паттерн 4: простое число
        if time_min is None:
            try:
                time_min = int(text)
            except ValueError:
                pass

        # Паттерн 5: "с 19 до 21", "19-21", "с 19:10 до 20:40", "19:30-21:00"
        if time_min is None:
            range_pattern = r'(?:с\s*)?(\d{1,2})(?::(\d{2}))?(?:\s*до\s*|\s*-\s*)(\d{1,2})(?::(\d{2}))?'
            match = re.search(range_pattern, text)

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

        # Сохраняем время
        context.user_data['time_per_session'] = time_min

        # Проверяем, есть ли уже сохранённый уровень подготовки
        user_settings = db.get_user_settings(user.id)
        existing_level = user_settings.get('fitness_level') if user_settings else None

        # Если нет — пробуем автоопределить по Garmin
        if not existing_level:
            from ...core.fitness_detector import detect_fitness_level
            detected_level, level_stats = detect_fitness_level(user.id)
            if detected_level:
                db.save_user_goal(user.id, fitness_level=detected_level)
                existing_level = detected_level
                logger.info(f"User {telegram_id}: автоопределён уровень {detected_level} при создании плана")

        if existing_level:
            # Уровень есть (сохранённый или автоопределённый) — сразу генерируем план
            from ...core.plan_generator import PlanGenerator

            goal_data = context.user_data.get('goal_data')
            selected_days = context.user_data.get('selected_days', [])

            level_names = {"beginner": "Новичок", "intermediate": "Средний", "advanced": "Опытный"}
            level_display = level_names.get(existing_level, existing_level)

            await update.message.reply_text(
                f"⏳ Генерирую план...\n\n"
                f"🎯 Цель: {goal_data['name']}\n"
                f"📅 Дней в неделю: {len(selected_days)}\n"
                f"⏱ Время на тренировку: {time_min} мин\n"
                f"🏃 Уровень: {level_display} (по Garmin)"
            )

            # Рассчитываем количество недель до забега
            days_until_race = (goal_data['date'] - time_utils.today()).days
            weeks = max(4, min(16, days_until_race // 7))

            generator = PlanGenerator(user.id)
            trainings = generator.generate_detailed_plan(
                goal_distance=goal_data['distance'],
                goal_date=goal_data['date'],
                training_days=selected_days,
                time_per_session=time_min,
                weeks=weeks,
                fitness_level=existing_level,
                goal_type=goal_data.get('type', 'race')
            )

            await update.message.reply_text(
                f"✅ План сгенерирован!\n\n"
                f"📅 До забега: {days_until_race} дней ({weeks} недель)\n"
                f"Создано {len(trainings)} тренировок.\n\n"
                f"Используй /plan чтобы посмотреть план на неделю."
            )

            return ConversationHandler.END

        # Уровня нет и не удалось автоопределить — спрашиваем вручную
        keyboard = [
            [InlineKeyboardButton("🟢 Новичок (бегаю < 6 месяцев)", callback_data="level_beginner")],
            [InlineKeyboardButton("🟡 Средний (6-24 месяца)", callback_data="level_intermediate")],
            [InlineKeyboardButton("🔴 Опытный (бегаю > 2 лет)", callback_data="level_advanced")]
        ]

        await update.message.reply_text(
            "🏃 Недостаточно данных в Garmin для определения уровня.\n\n"
            "Какой у тебя опыт в беге?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        context.user_data['awaiting_level'] = True
        return PLAN_TIME

    async def cancel_plan_creation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена создания плана"""
        await update.message.reply_text(
            "❌ Создание плана отменено\n\n"
            "Используй /plan чтобы начать заново"
        )
        return ConversationHandler.END
