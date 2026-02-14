"""Telegram алерты при критических ошибках"""
import os
import traceback
from datetime import datetime

import requests

from .logger import logger

# Алерты идут админу через основного бота
ADMIN_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "57186925"))
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Дедупликация: не слать один и тот же алерт чаще раза в 5 минут
_last_alerts: dict = {}
ALERT_COOLDOWN_SEC = 300


def send_alert(title: str, error: Exception = None, context: str = None):
    """
    Отправить алерт админу в Telegram

    Args:
        title: Краткое описание проблемы
        error: Исключение (опционально)
        context: Дополнительный контекст
    """
    if not BOT_TOKEN:
        logger.warning(f"Алерт не отправлен (нет BOT_TOKEN): {title}")
        return

    # Дедупликация
    now = datetime.now().timestamp()
    if title in _last_alerts and (now - _last_alerts[title]) < ALERT_COOLDOWN_SEC:
        logger.debug(f"Алерт подавлен (cooldown): {title}")
        return
    _last_alerts[title] = now

    # Формируем сообщение
    service = os.getenv("SERVICE_NAME", "unknown")
    msg = f"[{service}] {title}"

    if context:
        msg += f"\n\n{context}"

    if error:
        tb = traceback.format_exception(type(error), error, error.__traceback__)
        # Берем последние 500 символов traceback
        tb_text = "".join(tb)[-500:]
        msg += f"\n\n```\n{tb_text}\n```"

    # Обрезаем до лимита Telegram (4096 символов)
    if len(msg) > 4000:
        msg = msg[:4000] + "\n..."

    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": ADMIN_ID,
            "text": msg,
            "parse_mode": "Markdown",
            "disable_notification": False
        }, timeout=10)
        logger.info(f"Алерт отправлен: {title}")
    except Exception as e:
        logger.error(f"Не удалось отправить алерт: {e}")
