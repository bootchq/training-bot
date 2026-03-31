"""
Общий Groq клиент — единая точка инициализации.

Все AI модули (recovery_detector, smart_advisor, weekly_coach, workout_recommender)
импортируют отсюда вместо создания своих экземпляров OpenAI().

Модели Groq (по убыванию качества):
- llama-3.3-70b-versatile  — основной, лучшее качество
- llama-3.1-8b-instant     — быстрый, для простых задач
- gemma2-9b-it             — альтернатива
"""
from typing import Optional

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from ..utils.config import Config
from ..utils.logger import logger

# Модели
MODEL_MAIN = "llama-3.3-70b-versatile"
MODEL_FAST = "llama-3.1-8b-instant"

_client: Optional["OpenAI"] = None


def get_groq_client() -> Optional["OpenAI"]:
    """
    Получить инициализированный Groq клиент (singleton).

    Returns:
        OpenAI клиент с Groq base_url или None если ключ не задан
    """
    global _client

    if _client is not None:
        return _client

    if not Config.GROQ_API_KEY:
        logger.warning("GROQ_API_KEY не задан — AI функции отключены")
        return None

    if not OPENAI_AVAILABLE:
        logger.warning("openai пакет не установлен — AI функции отключены")
        return None

    _client = OpenAI(
        api_key=Config.GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1"
    )
    logger.info(f"Groq клиент инициализирован (model: {MODEL_MAIN})")
    return _client


def chat(
    system: str,
    user: str,
    model: str = MODEL_MAIN,
    max_tokens: int = 500,
    temperature: float = 0.7
) -> Optional[str]:
    """
    Простой helper для одиночного chat completion запроса.

    Args:
        system: System prompt
        user: User message
        model: Модель Groq
        max_tokens: Максимум токенов в ответе
        temperature: Температура (0.0–1.0)

    Returns:
        Текст ответа или None при ошибке
    """
    client = get_groq_client()
    if not client:
        return None

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            max_tokens=max_tokens,
            temperature=temperature
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Groq API ошибка: {e}")
        return None
