"""Fixtures для integration тестов"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, CallbackQuery, User, Message, Chat
from telegram.ext import ContextTypes


@pytest.fixture
def mock_user():
    """Мок пользователя Telegram"""
    # User - immutable объект, создаем через MagicMock с нужными атрибутами
    user = MagicMock()
    user.id = 12345
    user.first_name = "Test"
    user.is_bot = False
    user.username = "testuser"
    return user


@pytest.fixture
def mock_chat():
    """Мок чата Telegram"""
    return Chat(id=12345, type="private")


@pytest.fixture
def mock_message(mock_user, mock_chat):
    """Мок сообщения Telegram"""
    message = MagicMock(spec=Message)
    message.from_user = mock_user
    message.chat = mock_chat
    message.message_id = 1
    message.text = ""
    message.reply_text = AsyncMock()
    return message


@pytest.fixture
def mock_callback_query(mock_user, mock_message):
    """Мок callback_query для inline кнопок"""
    query = MagicMock(spec=CallbackQuery)
    query.from_user = mock_user
    query.message = mock_message
    query.data = ""
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.edit_message_reply_markup = AsyncMock()
    return query


@pytest.fixture
def mock_update(mock_user, mock_message, mock_callback_query):
    """Мок Update с поддержкой message и callback_query"""
    update = MagicMock(spec=Update)
    update.effective_user = mock_user
    update.effective_chat = mock_message.chat
    update.message = mock_message
    update.callback_query = mock_callback_query
    return update


@pytest.fixture
def mock_context():
    """Мок Context с user_data и bot_data"""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}
    context.bot_data = {}
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock()
    return context


@pytest.fixture
def mock_db():
    """Мок базы данных"""
    with patch('src.database.db.db') as mock:
        # Базовые методы БД
        mock.get_user_by_telegram_id = MagicMock(return_value=None)
        mock.create_user = MagicMock(return_value=MagicMock(id=1))
        mock.get_user_settings = MagicMock(return_value={})
        mock.update_user_settings = MagicMock()
        mock.get_user_by_id = MagicMock()
        mock.load_training_plan = MagicMock()
        yield mock


@pytest.fixture
def bot(mock_db):
    """Инстанс TrainingBot с мокнутой БД"""
    from src.bot.telegram_bot import TrainingBot

    # Мокаем Application чтобы не инициализировать настоящий бот
    with patch('src.bot.telegram_bot.Application') as mock_app:
        mock_app.builder.return_value.token.return_value.build.return_value = MagicMock()
        bot_instance = TrainingBot()
        return bot_instance
