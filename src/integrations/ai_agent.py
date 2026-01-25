"""AI-агент для разговора и изменения плана тренировок"""
import json
from datetime import date, timedelta
from typing import Dict, Any, Optional, List
from openai import OpenAI

from ..utils.config import Config
from ..utils.logger import logger
from ..database.db import db, TrainingPlan


class AIAgent:
    """AI-агент с возможностью изменения плана"""

    SYSTEM_PROMPT = """Ты — AI тренер по бегу. Твоя задача:
1. Отвечать на вопросы о тренировках
2. Помогать корректировать план
3. Давать советы по технике бега, питанию, восстановлению

У тебя есть инструменты для изменения плана:
- modify_workout: изменить конкретную тренировку
- swap_workouts: поменять местами две тренировки
- skip_workout: пропустить тренировку

Когда пользователь просит изменить план — используй инструменты.
Отвечай кратко, по делу, на русском языке.
"""

    TOOLS = [
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

            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT + f"\n\nКонтекст пользователя:\n{context}"},
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
        """Получить контекст пользователя для AI"""
        context_parts = []

        # Настройки пользователя
        settings = db.get_user_settings(user_id)
        if settings:
            goal_names = {
                'race': 'Забег',
                'weight_loss': 'Похудение',
                'endurance': 'Выносливость'
            }
            exp_names = {
                'beginner': 'Новичок',
                'intermediate': 'Средний',
                'advanced': 'Опытный'
            }

            context_parts.append(f"Цель: {goal_names.get(settings.get('goal_type'), 'Не указана')}")
            if settings.get('goal_distance_km'):
                context_parts.append(f"Дистанция: {settings['goal_distance_km']} км")
            if settings.get('goal_date'):
                context_parts.append(f"Дата забега: {settings['goal_date']}")
            context_parts.append(f"Опыт: {exp_names.get(settings.get('experience_level'), 'Не указан')}")

        # План на неделю
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())
        plans = db.get_plan_for_week(user_id, start_of_week)

        if plans:
            context_parts.append("\nПлан на неделю:")
            days_ru = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"}
            for plan in plans:
                day = days_ru.get(plan.date.weekday(), "")
                context_parts.append(f"  {day} {plan.date.strftime('%d.%m')}: {plan.type} ({plan.duration_min or '?'} мин)")

        context_parts.append(f"\nСегодня: {today.strftime('%d.%m.%Y')} ({['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'][today.weekday()]})")

        return "\n".join(context_parts)

    def _execute_tool(self, user_id: int, function_name: str, args: dict) -> dict:
        """Выполнить инструмент"""
        try:
            if function_name == "modify_workout":
                return self._modify_workout(user_id, args)
            elif function_name == "swap_workouts":
                return self._swap_workouts(user_id, args)
            elif function_name == "skip_workout":
                return self._skip_workout(user_id, args)
            elif function_name == "get_week_plan":
                return self._get_week_plan(user_id)
            else:
                return {"error": f"Неизвестная функция: {function_name}"}
        except Exception as e:
            logger.error(f"Ошибка выполнения {function_name}: {e}")
            return {"error": str(e)}

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

    def _get_week_plan(self, user_id: int) -> dict:
        """Получить план на неделю"""
        today = date.today()
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
