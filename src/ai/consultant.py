"""AI-консультант для анализа тренировок"""
from datetime import date, datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path
import json

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from ..database.db import db, Training, WellnessSurvey
from ..utils.logger import logger
from ..utils.config import Config


class TrainingConsultant:
    """AI-консультант на базе Groq (бесплатный)"""

    def __init__(self):
        """Инициализация консультанта"""
        self.api_key = Config.GROQ_API_KEY or Config.ANTHROPIC_API_KEY

        if self.api_key and OPENAI_AVAILABLE:
            # Groq использует OpenAI-совместимый API
            self.client = OpenAI(
                api_key=self.api_key,
                base_url="https://api.groq.com/openai/v1"
            )
            self.model = "llama-3.1-70b-versatile"  # Groq модель (бесплатно)
            logger.info("AI-консультант инициализирован (Groq)")
        else:
            self.client = None
            if not OPENAI_AVAILABLE:
                logger.warning("Библиотека openai не установлена")
            else:
                logger.warning("GROQ_API_KEY не установлен, AI-консультант недоступен")

        self.daily_limit = 100  # Groq: больший лимит (бесплатно)
        self.usage_file = Path(Config.DATA_DIR) / 'ai_usage.json'

    def get_training_advice(
        self,
        user_id: int,
        training_date: date,
        wellness_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Получить совет AI по тренировке

        Args:
            user_id: ID пользователя
            training_date: Дата тренировки
            wellness_data: Данные из опроса самочувствия

        Returns:
            Совет от AI или шаблонное сообщение при превышении лимита
        """
        if not self.client:
            return self._get_template_advice(training_date)

        # Проверяем лимит
        if not self._check_daily_limit(user_id):
            logger.info(f"Превышен дневной лимит AI для пользователя {user_id}")
            return self._get_template_advice(training_date)

        # Получаем данные тренировки
        training = db.get_training_for_date(user_id, training_date)

        if not training:
            return "Тренировка не найдена в базе данных"

        # Формируем промпт
        prompt = self._build_prompt(training, wellness_data)

        try:
            # Запрос к Groq (OpenAI-совместимый API)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Ты - опытный тренер по бегу, специализирующийся на ультрамарафонах и трейлраннинге. Даёшь короткие практические советы на русском языке."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=500,
                temperature=0.7
            )

            advice = response.choices[0].message.content

            # Увеличиваем счётчик использования
            self._increment_usage(user_id)

            logger.info(f"AI совет получен для пользователя {user_id} (Groq)")
            return advice

        except Exception as e:
            logger.error(f"Ошибка запроса к Groq API: {e}")
            return self._get_template_advice(training_date)

    def _build_prompt(
        self,
        training: Training,
        wellness_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Формирование промпта для Claude

        Args:
            training: Данные тренировки
            wellness_data: Данные опроса самочувствия

        Returns:
            Промпт для AI
        """
        prompt = f"""Ты - тренер по бегу, специализирующийся на ультрамарафонах и трейлраннинге.

Проанализируй тренировку и дай короткий совет (2-3 предложения).

**Данные тренировки:**
- Дата: {training.date.strftime('%d.%m.%Y')}
- Дистанция: {training.distance_km:.1f} км
- Время: {training.duration_min} мин
- Темп: {training.avg_pace or 'не указан'}
- Средний пульс: {training.avg_hr or 'не указан'} bpm
- Макс пульс: {training.max_hr or 'не указан'} bpm
"""

        # Добавляем зоны пульса если есть
        if training.hr_zones:
            prompt += f"\n**Время в зонах пульса:**\n"
            for zone, minutes in training.hr_zones.items():
                if minutes > 0:
                    prompt += f"- {zone.upper()}: {minutes} мин\n"

        # Добавляем данные опроса если есть
        if wellness_data:
            prompt += f"\n**Самочувствие после тренировки:**\n"
            prompt += f"- Оценка тренировки: {wellness_data.get('training_rating', 'не указана')}/10\n"
            prompt += f"- Общее самочувствие: {self._wellness_to_text(wellness_data.get('wellness_rating'))}\n"
            prompt += f"- Боль/дискомфорт: {'Да' if wellness_data.get('pain_reported') else 'Нет'}\n"
            prompt += f"- Качество сна: {wellness_data.get('sleep_quality', 'не указано')}\n"

        prompt += """
**Твоя задача:**
Дай короткий практический совет (2-3 предложения):
- Оцени выполнение тренировки (темп, пульс, зоны)
- Что улучшить в следующий раз
- Рекомендации по восстановлению (если нужно)

Отвечай на русском языке, дружелюбно и мотивирующе.
"""

        return prompt

    def _wellness_to_text(self, wellness_rating: Optional[int]) -> str:
        """Конвертация числового рейтинга в текст"""
        if wellness_rating == 1:
            return "усталость"
        elif wellness_rating == 2:
            return "норма"
        elif wellness_rating == 3:
            return "отлично"
        else:
            return "не указано"

    def _check_daily_limit(self, user_id: int) -> bool:
        """
        Проверка дневного лимита запросов

        Args:
            user_id: ID пользователя

        Returns:
            True если лимит не превышен
        """
        usage = self._load_usage()
        today = datetime.now().strftime('%Y-%m-%d')
        user_key = f"{user_id}_{today}"

        current_count = usage.get(user_key, 0)
        return current_count < self.daily_limit

    def _increment_usage(self, user_id: int):
        """
        Увеличить счётчик использования

        Args:
            user_id: ID пользователя
        """
        usage = self._load_usage()
        today = datetime.now().strftime('%Y-%m-%d')
        user_key = f"{user_id}_{today}"

        usage[user_key] = usage.get(user_key, 0) + 1

        # Удаляем старые записи (старше 7 дней)
        self._cleanup_old_usage(usage)

        self._save_usage(usage)

    def _load_usage(self) -> Dict[str, int]:
        """Загрузка данных использования из файла"""
        if not self.usage_file.exists():
            return {}

        try:
            with open(self.usage_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки данных использования: {e}")
            return {}

    def _save_usage(self, usage: Dict[str, int]):
        """Сохранение данных использования в файл"""
        try:
            with open(self.usage_file, 'w') as f:
                json.dump(usage, f, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения данных использования: {e}")

    def _cleanup_old_usage(self, usage: Dict[str, int]):
        """Удаление записей старше 7 дней"""
        cutoff = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

        # Создаём новый словарь без старых записей
        keys_to_remove = []
        for key in usage.keys():
            # Формат ключа: "user_id_YYYY-MM-DD"
            parts = key.split('_')
            if len(parts) >= 3:
                key_date = '_'.join(parts[-3:])  # Берём последние 3 части (дата)
                if key_date < cutoff:
                    keys_to_remove.append(key)

        for key in keys_to_remove:
            del usage[key]

    def _get_template_advice(self, training_date: date) -> str:
        """
        Шаблонный совет при превышении лимита или ошибке

        Args:
            training_date: Дата тренировки

        Returns:
            Шаблонный совет
        """
        templates = [
            "Отличная работа! Продолжай придерживаться плана и слушай своё тело.",
            "Хорошая тренировка! Не забывай про восстановление и качественный сон.",
            "Молодец! Следующая тренировка - возможность улучшить результат.",
            "Так держать! Помни про правило 10%: не увеличивай объём больше чем на 10% в неделю.",
            "Отлично! После тяжёлой тренировки обязательно дай себе восстановиться."
        ]

        # Выбираем шаблон по дню месяца (чтобы было разнообразие)
        template_index = training_date.day % len(templates)
        return templates[template_index]


# Глобальный экземпляр
consultant = TrainingConsultant()
