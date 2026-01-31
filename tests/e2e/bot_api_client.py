"""
Клиент для тестирования бота через Telegram Bot API.
Не требует api_id/api_hash — только токен бота.
"""

import time
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import requests


class BotApiClient:
    """HTTP клиент для Bot API (getUpdates + sendMessage)."""

    def __init__(self, token: str, chat_id: int):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}"
        self._offset: Optional[int] = None

    def _request(self, method: str, **params: Any) -> Any:
        """Отправка запроса к Bot API."""
        resp = requests.post(
            f"{self.base_url}/{method}",
            json=params,
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API error: {data}")
        return data["result"]

    def send_message(self, text: str) -> Dict[str, Any]:
        """Отправить текстовое сообщение боту."""
        return self._request("sendMessage", chat_id=self.chat_id, text=text)

    def get_updates(self, timeout: int = 25) -> List[Dict[str, Any]]:
        """Получить обновления (long polling)."""
        params: Dict[str, Any] = {"timeout": timeout}
        if self._offset is not None:
            params["offset"] = self._offset

        result = self._request("getUpdates", **params)

        if result:
            # Сдвигаем offset чтобы не получать старые апдейты
            self._offset = result[-1]["update_id"] + 1

        return result

    def wait_for_message(
        self,
        from_bot: bool = True,
        timeout: int = 30,
        text_contains: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Ждет следующее сообщение от бота или пользователя.

        Args:
            from_bot: True = ждать сообщение от бота, False = от пользователя
            timeout: таймаут ожидания
            text_contains: если задано, ждет пока текст содержит эту подстроку
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            updates = self.get_updates(timeout=5)
            for upd in updates:
                msg = upd.get("message") or upd.get("edited_message")
                if not msg:
                    continue

                # Проверяем что это наш чат
                if msg.get("chat", {}).get("id") != self.chat_id:
                    continue

                # Проверяем что сообщение от бота/пользователя
                is_bot = msg.get("from", {}).get("is_bot", False)
                if from_bot and not is_bot:
                    continue
                if not from_bot and is_bot:
                    continue

                # Проверяем текст если нужно
                if text_contains:
                    text = msg.get("text", "")
                    if text_contains.lower() not in text.lower():
                        continue

                return msg

        raise TimeoutError(
            f"No message received within {timeout}s "
            f"(from_bot={from_bot}, text_contains={text_contains})"
        )

    def wait_for_callback_query(self, timeout: int = 30) -> Dict[str, Any]:
        """Ждет callback_query (нажатие на inline кнопку)."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            updates = self.get_updates(timeout=5)
            for upd in updates:
                cq = upd.get("callback_query")
                if not cq:
                    continue

                # Проверяем что это наш чат
                msg = cq.get("message", {})
                if msg.get("chat", {}).get("id") != self.chat_id:
                    continue

                return cq

        raise TimeoutError(f"No callback_query within {timeout}s")

    def click_inline_button(self, message: Dict[str, Any], button_text: str) -> None:
        """
        Эмулирует клик по inline кнопке.

        Args:
            message: сообщение с кнопками (от wait_for_message)
            button_text: текст кнопки (с emoji или без)
        """
        reply_markup = message.get("reply_markup", {})
        keyboard = reply_markup.get("inline_keyboard", [])

        # Ищем кнопку по тексту
        callback_data = None
        for row in keyboard:
            for btn in row:
                if button_text.lower() in btn.get("text", "").lower():
                    callback_data = btn.get("callback_data")
                    break
            if callback_data:
                break

        if not callback_data:
            available = []
            for row in keyboard:
                for btn in row:
                    available.append(btn.get("text", ""))
            raise ValueError(
                f"Button '{button_text}' not found. "
                f"Available: {available}"
            )

        # Отправляем callback_data через answerCallbackQuery
        # (в реальности это делает клиент автоматически, но мы эмулируем)
        # Для тестирования нужно отправить sendMessage с callback_data
        # НО Bot API не позволяет отправлять callback_query напрямую
        # Поэтому используем обходной путь: просто отправляем текст кнопки
        # и бот должен обработать это через CallbackQueryHandler

        # ВАЖНО: это работает только если бот ожидает callback_data
        # В реальности нужно использовать другой подход — см. ниже

        print(f"[DEBUG] Clicking button: {button_text} (callback_data: {callback_data})")

        # Здесь проблема: Bot API не позволяет отправлять callback_query от имени пользователя
        # Нужно использовать MTProto (Telethon) или pytest-telegram-bot
        raise NotImplementedError(
            "Bot API не позволяет эмулировать клик по inline кнопке. "
            "Используй MTProto (Telethon) или pytest с mock."
        )

    def get_inline_buttons(self, message: Dict[str, Any]) -> List[str]:
        """Получить список текстов всех inline кнопок."""
        reply_markup = message.get("reply_markup", {})
        keyboard = reply_markup.get("inline_keyboard", [])

        buttons = []
        for row in keyboard:
            for btn in row:
                buttons.append(btn.get("text", ""))

        return buttons

    def reset_offset(self) -> None:
        """Сбросить offset (начать читать апдейты с начала)."""
        # Получаем все апдейты и пропускаем их
        updates = self.get_updates(timeout=1)
        if updates:
            self._offset = updates[-1]["update_id"] + 1
