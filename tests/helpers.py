"""
Helpers для тестирования бота.
Создание mock Update и Context объектов.
"""

from datetime import datetime
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

from telegram import CallbackQuery
from telegram import Chat
from telegram import Message
from telegram import Update
from telegram import User
from telegram.ext import ContextTypes


def create_user(user_id: int = 12345, username: str = "testuser") -> User:
    """Создать тестового пользователя."""
    return User(
        id=user_id,
        first_name="Test",
        is_bot=False,
        username=username
    )


def create_chat(chat_id: int = 12345) -> Chat:
    """Создать тестовый чат."""
    return Chat(id=chat_id, type="private")


def create_message(
    text: str = "/start",
    user: User = None,
    chat: Chat = None,
    message_id: int = 1
) -> Message:
    """Создать тестовое сообщение."""
    if user is None:
        user = create_user()
    if chat is None:
        chat = create_chat()

    return Message(
        message_id=message_id,
        date=datetime.now(),
        chat=chat,
        from_user=user,
        text=text
    )


def create_text_update(
    text: str = "/start",
    user_id: int = 12345,
    chat_id: int = 12345,
    update_id: int = 1
) -> Update:
    """Создать Update с текстовым сообщением."""
    user = create_user(user_id=user_id)
    chat = create_chat(chat_id=chat_id)
    message = create_message(text=text, user=user, chat=chat)

    return Update(update_id=update_id, message=message)


def create_callback_update(
    callback_data: str,
    user_id: int = 12345,
    chat_id: int = 12345,
    update_id: int = 1,
    message_text: str = ""
) -> Update:
    """Создать Update с callback_query (клик по inline кнопке)."""
    user = create_user(user_id=user_id)
    chat = create_chat(chat_id=chat_id)
    message = create_message(text=message_text, user=user, chat=chat)

    callback_query = CallbackQuery(
        id=str(update_id),
        from_user=user,
        chat_instance=str(chat_id),
        message=message,
        data=callback_data
    )
    callback_query._unfreeze()
    callback_query.answer = AsyncMock()

    return Update(update_id=update_id, callback_query=callback_query)


def create_context(user_data: dict = None) -> MagicMock:
    """Создать mock Context."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot = AsyncMock()
    context.bot.send_message = AsyncMock(return_value=create_message())
    context.bot.edit_message_reply_markup = AsyncMock()
    context.bot.edit_message_text = AsyncMock()
    context.user_data = user_data or {}
    context.chat_data = {}
    context.bot_data = {}

    return context


def extract_buttons(reply_markup) -> list[str]:
    """Извлечь тексты кнопок из reply_markup."""
    if not reply_markup:
        return []

    buttons = []
    if hasattr(reply_markup, "inline_keyboard"):
        for row in reply_markup.inline_keyboard:
            for btn in row:
                buttons.append(btn.text)
    return buttons


def extract_callback_data(reply_markup) -> list[str]:
    """Извлечь callback_data из всех кнопок."""
    if not reply_markup:
        return []

    data = []
    if hasattr(reply_markup, "inline_keyboard"):
        for row in reply_markup.inline_keyboard:
            for btn in row:
                if btn.callback_data:
                    data.append(btn.callback_data)
    return data


def find_button_callback(reply_markup, button_text: str) -> str:
    """Найти callback_data кнопки по тексту."""
    if not reply_markup:
        return None

    if hasattr(reply_markup, "inline_keyboard"):
        for row in reply_markup.inline_keyboard:
            for btn in row:
                if button_text.lower() in btn.text.lower():
                    return btn.callback_data
    return None
