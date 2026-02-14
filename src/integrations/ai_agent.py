"""AI-агент для разговора и изменения плана тренировок"""
import json
from datetime import date
from datetime import timedelta

from openai import OpenAI

from ..database.db import TrainingPlan
from ..database.db import db
from ..utils import time_utils
from ..utils.config import Config
from ..utils.logger import logger


class AIAgent:
    """AI-агент с возможностью изменения плана"""

    SYSTEM_PROMPT_TEMPLATE = """Ты — AI тренер по бегу.

СЕГОДНЯ: {today} ({weekday}). Используй эту дату во всех ответах.

Твоя задача:
1. Отвечать на вопросы о тренировках
2. Помогать корректировать и генерировать план
3. Давать советы по технике бега, питанию, восстановлению
4. Анализировать историю тренировок пользователя (синхронизированы с Garmin)
5. Рекомендовать тренировки на основе реальных данных

У тебя есть ПОЛНЫЙ ДОСТУП к истории тренировок пользователя из Garmin Connect.
В контексте ниже — его реальные тренировки за последние 4 недели, VDOT, LTHR, план.

У тебя есть инструменты:
- generate_week_plan: СГЕНЕРИРОВАТЬ новый план на неделю (персонализированный, по VDOT/LTHR)
- modify_workout: изменить конкретную тренировку
- swap_workouts: поменять местами две тренировки
- skip_workout: пропустить тренировку
- get_week_plan: посмотреть текущий план на неделю
- get_recent_trainings: получить историю тренировок

ВАЖНО:
- Когда пользователь просит план/тренировки на неделю — ВСЕГДА используй generate_week_plan.
- НЕ выдумывай тренировки сам — используй инструмент, он учитывает VDOT, LTHR, историю.
- Когда tool возвращает план — ПОКАЖИ ЕГО КАК ЕСТЬ, не пересказывай и не упрощай.
- Каждая тренировка содержит описание с зонами, разминкой, заминкой — покажи всё.
- НЕ заменяй описание на "8 км темп 6:45" — это бесполезно.
Отвечай кратко, по делу, на русском языке.
"""

    TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "generate_week_plan",
                "description": "Сгенерировать персонализированный план тренировок на неделю. Использует VDOT, LTHR, историю с Garmin, цель пользователя.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "weeks": {
                            "type": "integer",
                            "description": "Количество недель плана (по умолчанию 1)"
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "modify_workout",
                "description": "Изменить параметры тренировки на конкретную дату",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date": {
                            "type": "string",
                            "description": "Дата тренировки в формате YYYY-MM-DD"
                        },
                        "workout_type": {
                            "type": "string",
                            "description": "Новый тип тренировки (Интервалы, Длинная, Темповый, Восстановительная, Лёгкая)"
                        },
                        "duration_min": {
                            "type": "integer",
                            "description": "Новая длительность в минутах"
                        },
                        "distance_km": {
                            "type": "number",
                            "description": "Новая дистанция в км"
                        },
                        "description": {
                            "type": "string",
                            "description": "Новое описание тренировки"
                        }
                    },
                    "required": ["date"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "swap_workouts",
                "description": "Поменять местами тренировки двух дней",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date1": {
                            "type": "string",
                            "description": "Первая дата в формате YYYY-MM-DD"
                        },
                        "date2": {
                            "type": "string",
                            "description": "Вторая дата в формате YYYY-MM-DD"
                        }
                    },
                    "required": ["date1", "date2"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "skip_workout",
                "description": "Пропустить тренировку на дату",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date": {
                            "type": "string",
                            "description": "Дата тренировки в формате YYYY-MM-DD"
                        },
                        "reason": {
                            "type": "string",
                            "description": "Причина пропуска"
                        }
                    },
                    "required": ["date"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_week_plan",
                "description": "Получить план на текущую неделю",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_recent_trainings",
                "description": "Получить историю тренировок с Garmin за указанное количество недель",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "weeks": {
                            "type": "integer",
                            "description": "Количество недель (1-12, по умолчанию 4)"
                        }
                    },
                    "required": []
                }
            }
        }
    ]

    def __init__(self):
        """Инициализация"""
        # Используем Groq API (совместим с OpenAI SDK)
        if Config.GROQ_API_KEY:
            self.client = OpenAI(
                api_key=Config.GROQ_API_KEY,
                base_url="https://api.groq.com/openai/v1"
            )
            self.model = "llama-3.3-70b-versatile"
            logger.info("AI-агент инициализирован (Groq)")
        elif Config.OPENAI_API_KEY:
            self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
            self.model = "gpt-4o-mini"
            logger.info("AI-агент инициализирован (OpenAI)")
        else:
            self.client = None
            logger.warning("AI-агент не настроен: нет API ключа")

    async def chat(self, user_id: int, message: str) -> str:
        """
        Обработать сообщение пользователя

        Args:
            user_id: ID пользователя
            message: Текст сообщения

        Returns:
            Ответ AI
        """
        if not self.client:
            return "AI-консультант недоступен. Настрой GROQ_API_KEY в .env"

        try:
            # Получаем контекст пользователя
            context = self._get_user_context(user_id)

            # Динамический system prompt с актуальной датой
            today = time_utils.today()
            days_ru = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
            system_prompt = self.SYSTEM_PROMPT_TEMPLATE.format(
                today=today.strftime('%d.%m.%Y'),
                weekday=days_ru[today.weekday()]
            )

            messages = [
                {"role": "system", "content": system_prompt + f"\n\nКонтекст пользователя:\n{context}"},
                {"role": "user", "content": message}
            ]

            # Первый вызов с tools
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.TOOLS,
                tool_choice="auto"
            )

            assistant_message = response.choices[0].message

            # Если есть tool calls — выполняем их
            if assistant_message.tool_calls:
                messages.append(assistant_message)

                for tool_call in assistant_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)

                    # Выполняем функцию
                    result = self._execute_tool(user_id, function_name, function_args)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result, ensure_ascii=False)
                    })

                # Второй вызов для финального ответа
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages
                )

                return response.choices[0].message.content

            return assistant_message.content

        except Exception as e:
            logger.error(f"Ошибка AI-агента: {e}")
            return f"Произошла ошибка: {e}"

    def _get_user_context(self, user_id: int) -> str:
        """Получить полный контекст пользователя для AI (включая тренировки с Garmin)"""
        context_parts = []

        # Настройки пользователя
        settings = db.get_user_settings(user_id)
        if settings:
            goal_names = {
                'race': 'Забег',
                'trail': 'Трейл',
                'weight_loss': 'Похудение',
                'endurance': 'Выносливость',
                'fitness': 'Фитнес'
            }
            exp_names = {
                'beginner': 'Новичок',
                'intermediate': 'Средний',
                'advanced': 'Опытный'
            }

            context_parts.append(f"Цель: {goal_names.get(settings.get('goal_type'), settings.get('goal_type', 'Не указана'))}")
            if settings.get('goal_distance_km'):
                context_parts.append(f"Дистанция цели: {settings['goal_distance_km']} км")
            if settings.get('goal_date'):
                context_parts.append(f"Дата забега: {settings['goal_date']}")
            if settings.get('goal_elevation_gain'):
                context_parts.append(f"Набор высоты цели: {settings['goal_elevation_gain']} м")
            context_parts.append(f"Опыт: {exp_names.get(settings.get('experience_level'), 'Не указан')}")

            # VDOT и LTHR
            if settings.get('vdot'):
                context_parts.append(f"VDOT: {settings['vdot']:.1f} (Jack Daniels)")
            if settings.get('lthr'):
                context_parts.append(f"LTHR: {settings['lthr']} уд/мин")

        # Последние тренировки с Garmin (за 4 недели)
        today = time_utils.today()
        four_weeks_ago = today - timedelta(days=28)
        trainings = db.get_trainings_for_period(user_id, four_weeks_ago, today)

        if trainings:
            total_km = sum(t.distance_km or 0 for t in trainings)
            total_min = sum(t.duration_min or 0 for t in trainings)
            avg_weekly_km = total_km / 4

            context_parts.append("\n--- Тренировки с Garmin (последние 4 недели) ---")
            context_parts.append(f"Всего тренировок: {len(trainings)}")
            context_parts.append(f"Общая дистанция: {total_km:.1f} км ({avg_weekly_km:.1f} км/нед)")
            context_parts.append(f"Общее время: {total_min} мин")

            days_ru = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"}

            context_parts.append("\nПоследние тренировки:")
            for t in trainings[-10:]:  # Последние 10
                day = days_ru.get(t.date.weekday(), "") if t.date else ""
                pace_str = ""
                if t.distance_km and t.duration_min and t.distance_km > 0:
                    pace_sec = (t.duration_min * 60) / t.distance_km
                    pace_str = f", темп {int(pace_sec)//60}:{int(pace_sec)%60:02d}/км"
                hr_str = f", пульс ср {t.avg_hr}" if t.avg_hr else ""
                elev_str = f", набор {t.elevation_m}м" if t.elevation_m else ""
                context_parts.append(
                    f"  {day} {t.date.strftime('%d.%m') if t.date else '?'}: "
                    f"{t.distance_km or 0:.1f} км, {t.duration_min or 0} мин"
                    f"{pace_str}{hr_str}{elev_str}"
                )
        else:
            context_parts.append("\n--- Тренировки с Garmin: нет данных за последние 4 недели ---")

        # План на неделю
        start_of_week = today - timedelta(days=today.weekday())
        plans = db.get_plan_for_week(user_id, start_of_week)

        if plans:
            context_parts.append("\n--- План на текущую неделю ---")
            days_ru = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"}
            for plan in plans:
                day = days_ru.get(plan.date.weekday(), "")
                status = "✓" if plan.is_completed else "○"
                context_parts.append(
                    f"  {status} {day} {plan.date.strftime('%d.%m')}: {plan.type} "
                    f"({plan.duration_min or '?'} мин, {plan.distance_km or '?'} км)"
                )

        context_parts.append(f"\nСегодня: {today.strftime('%d.%m.%Y')} ({['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'][today.weekday()]})")

        return "\n".join(context_parts)

    def _execute_tool(self, user_id: int, function_name: str, args: dict) -> dict:
        """Выполнить инструмент"""
        try:
            if function_name == "generate_week_plan":
                return self._generate_week_plan(user_id, args)
            elif function_name == "modify_workout":
                return self._modify_workout(user_id, args)
            elif function_name == "swap_workouts":
                return self._swap_workouts(user_id, args)
            elif function_name == "skip_workout":
                return self._skip_workout(user_id, args)
            elif function_name == "get_week_plan":
                return self._get_week_plan(user_id)
            elif function_name == "get_recent_trainings":
                return self._get_recent_trainings(user_id, args)
            else:
                return {"error": f"Неизвестная функция: {function_name}"}
        except Exception as e:
            logger.error(f"Ошибка выполнения {function_name}: {e}")
            return {"error": str(e)}

    def _generate_week_plan(self, user_id: int, args: dict) -> dict:
        """Сгенерировать план на неделю через PlanGenerator"""
        from ..core.plan_generator import PlanGenerator

        today = time_utils.today()
        weeks = min(args.get('weeks', 1), 4)

        # Получаем настройки пользователя
        settings = db.get_user_settings(user_id)
        if not settings:
            return {"error": "Настройки пользователя не найдены. Пройди /start для настройки."}

        goal_type = settings.get('goal_type') or 'race'
        goal_distance = settings.get('goal_distance_km') or 21
        goal_date_str = settings.get('goal_date')
        training_days_str = settings.get('training_days') or '1,3,5'

        # Парсим дни тренировок
        try:
            training_days = [int(d.strip()) for d in str(training_days_str).split(',') if d.strip()]
        except (ValueError, AttributeError):
            training_days = [1, 3, 5]

        # Дата забега
        if goal_date_str:
            try:
                goal_date = date.fromisoformat(str(goal_date_str)[:10])
            except ValueError:
                goal_date = today + timedelta(weeks=12)
        else:
            goal_date = today + timedelta(weeks=12)

        # Генерируем план
        generator = PlanGenerator(user_id)
        trainings = generator.generate_detailed_plan(
            goal_distance=int(goal_distance or 21),
            goal_date=goal_date,
            training_days=training_days,
            time_per_session=60,
            weeks=weeks,
            goal_type=goal_type,
            fitness_level=settings.get('experience_level')
        )

        # Сохраняем в БД
        count = generator.save_plan_to_db(trainings)
        logger.info(f"AI сгенерировал план: {count} тренировок на {weeks} нед для user_id={user_id}")

        # Возвращаем читаемый текстовый формат (AI должен показать как есть)
        days_ru = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"}
        plan_text = f"План на {weeks} нед создан ({count} тренировок):\n\n"
        for t in trainings:
            t_date = t.get('date')
            if t_date:
                day_name = days_ru.get(t_date.weekday(), "")
                zone = t.get('target_zone', '')
                duration = t.get('duration_min', '?')
                distance = t.get('distance_km', '?')
                goal = t.get('goal', '')
                desc = t.get('description', '')

                plan_text += f"📅 {day_name} {t_date.strftime('%d.%m')} — {t.get('type', 'easy').upper()}"
                plan_text += f" | {duration} мин | ~{distance} км | {zone}\n"
                if goal:
                    plan_text += f"   {goal}\n"
                if desc:
                    plan_text += f"   {desc}\n"
                plan_text += "\n"

        return {
            "plan_text": plan_text,
            "total_workouts": count,
            "message": "ПОКАЖИ ПЛАН ПОЛЬЗОВАТЕЛЮ КАК ЕСТЬ, НЕ ПЕРЕСКАЗЫВАЙ И НЕ УПРОЩАЙ"
        }

    def _modify_workout(self, user_id: int, args: dict) -> dict:
        """Изменить тренировку"""
        target_date = date.fromisoformat(args['date'])

        with db.get_session() as session:
            plan = session.query(TrainingPlan).filter_by(
                user_id=user_id,
                date=target_date
            ).first()

            if not plan:
                return {"error": f"Тренировка на {target_date} не найдена"}

            if 'workout_type' in args:
                plan.type = args['workout_type']
            if 'duration_min' in args:
                plan.duration_min = args['duration_min']
            if 'distance_km' in args:
                plan.distance_km = args['distance_km']
            if 'description' in args:
                plan.description = args['description']

            logger.info(f"Тренировка на {target_date} изменена для user_id={user_id}")
            return {"success": True, "message": f"Тренировка на {target_date.strftime('%d.%m')} изменена"}

    def _swap_workouts(self, user_id: int, args: dict) -> dict:
        """Поменять местами тренировки"""
        date1 = date.fromisoformat(args['date1'])
        date2 = date.fromisoformat(args['date2'])

        with db.get_session() as session:
            plan1 = session.query(TrainingPlan).filter_by(user_id=user_id, date=date1).first()
            plan2 = session.query(TrainingPlan).filter_by(user_id=user_id, date=date2).first()

            if not plan1 or not plan2:
                return {"error": "Одна из тренировок не найдена"}

            # Меняем местами
            plan1.date, plan2.date = plan2.date, plan1.date

            logger.info(f"Тренировки {date1} и {date2} поменяны местами для user_id={user_id}")
            return {"success": True, "message": f"Тренировки {date1.strftime('%d.%m')} и {date2.strftime('%d.%m')} поменяны местами"}

    def _skip_workout(self, user_id: int, args: dict) -> dict:
        """Пропустить тренировку"""
        target_date = date.fromisoformat(args['date'])
        reason = args.get('reason', 'Не указана')

        with db.get_session() as session:
            plan = session.query(TrainingPlan).filter_by(
                user_id=user_id,
                date=target_date
            ).first()

            if not plan:
                return {"error": f"Тренировка на {target_date} не найдена"}

            # Помечаем как выполненную (пропущенную)
            plan.is_completed = True
            plan.description = f"[ПРОПУЩЕНО: {reason}] {plan.description or ''}"

            logger.info(f"Тренировка на {target_date} пропущена для user_id={user_id}")
            return {"success": True, "message": f"Тренировка на {target_date.strftime('%d.%m')} пропущена"}

    def _get_recent_trainings(self, user_id: int, args: dict) -> dict:
        """Получить историю тренировок за N недель"""
        weeks = min(args.get('weeks', 4), 12)
        today = time_utils.today()
        start_date = today - timedelta(days=weeks * 7)
        trainings = db.get_trainings_for_period(user_id, start_date, today)

        if not trainings:
            return {"message": f"Нет тренировок за последние {weeks} недель"}

        result = []
        days_ru = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"}
        total_km = 0
        total_min = 0

        for t in trainings:
            day = days_ru.get(t.date.weekday(), "") if t.date else ""
            pace_str = ""
            if t.distance_km and t.duration_min and t.distance_km > 0:
                pace_sec = (t.duration_min * 60) / t.distance_km
                pace_str = f"{int(pace_sec)//60}:{int(pace_sec)%60:02d}/км"
            total_km += t.distance_km or 0
            total_min += t.duration_min or 0

            result.append({
                "date": t.date.isoformat() if t.date else None,
                "day": day,
                "distance_km": t.distance_km,
                "duration_min": t.duration_min,
                "avg_hr": t.avg_hr,
                "max_hr": t.max_hr,
                "avg_pace": pace_str,
                "elevation_m": t.elevation_m,
            })

        return {
            "trainings": result,
            "summary": {
                "count": len(trainings),
                "total_km": round(total_km, 1),
                "total_min": total_min,
                "avg_weekly_km": round(total_km / max(weeks, 1), 1),
                "avg_weekly_sessions": round(len(trainings) / max(weeks, 1), 1),
            }
        }

    def _get_week_plan(self, user_id: int) -> dict:
        """Получить план на неделю"""
        today = time_utils.today()
        start_of_week = today - timedelta(days=today.weekday())
        plans = db.get_plan_for_week(user_id, start_of_week)

        if not plans:
            return {"message": "План на неделю не найден"}

        result = []
        days_ru = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"}
        for plan in plans:
            result.append({
                "date": plan.date.isoformat(),
                "day": days_ru.get(plan.date.weekday(), ""),
                "type": plan.type,
                "duration_min": plan.duration_min,
                "distance_km": plan.distance_km,
                "completed": plan.is_completed
            })

        return {"plan": result}


# Глобальный экземпляр
ai_agent = AIAgent()


# Обратная совместимость с ai_consultant
class AIConsultant:
    """Обёртка для совместимости"""

    def __init__(self):
        """Инициализация"""
        self.client = ai_agent.client
        self.model = ai_agent.model

    def ask(self, prompt: str) -> str:
        """
        Синхронный вопрос к AI (без контекста пользователя)

        Args:
            prompt: Текст вопроса

        Returns:
            Ответ AI
        """
        if not self.client:
            return "AI-консультант недоступен"

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Ошибка AI-консультанта: {e}")
            return f"Ошибка: {e}"

    async def get_advice(self, user_id: int, context: str, training_data: dict = None) -> str:
        """Получить совет от AI"""
        return await ai_agent.chat(user_id, context)


ai_consultant = AIConsultant()
