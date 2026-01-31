"""
Pytest fixtures для E2E тестирования через Telethon.
"""

import asyncio
import os
from collections.abc import AsyncGenerator

import pytest

# Загружаем .env.e2e
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '../../.env.e2e'))

from telethon import TelegramClient
from telethon.sessions import StringSession

# Конфигурация
API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
SESSION = os.getenv("TELETHON_SESSION", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "training_dag_run_bot")
GARMIN_EMAIL = os.getenv("GARMIN_TEST_EMAIL", "")
GARMIN_PASSWORD = os.getenv("GARMIN_TEST_PASSWORD", "")
TIMEOUT = int(os.getenv("E2E_TIMEOUT", "30"))
MESSAGE_WAIT = int(os.getenv("E2E_MESSAGE_WAIT", "5"))


@pytest.fixture(scope="session")
def event_loop():
    """Один event loop для всей сессии тестов."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def client() -> AsyncGenerator[TelegramClient, None]:
    """
    Telethon клиент с сохраненной сессией.
    Используется для всех тестов.
    """
    if not API_ID or not API_HASH or not SESSION:
        pytest.skip("Не настроены TELEGRAM_API_ID, TELEGRAM_API_HASH или TELETHON_SESSION")

    client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        pytest.fail("Сессия невалидна. Перегенерируй через scripts/generate_telethon_session.py")

    yield client

    await client.disconnect()


@pytest.fixture(scope="session")
def bot_username() -> str:
    """Username бота для тестирования."""
    return BOT_USERNAME


@pytest.fixture(scope="session")
def garmin_credentials() -> tuple[str, str]:
    """Тестовые Garmin credentials."""
    return (GARMIN_EMAIL, GARMIN_PASSWORD)


@pytest.fixture(scope="session")
def timeout() -> int:
    """Таймаут ожидания ответа бота."""
    return TIMEOUT


@pytest.fixture(scope="session")
def message_wait() -> int:
    """Время ожидания между сообщениями."""
    return MESSAGE_WAIT


@pytest.fixture
async def reset_bot(client: TelegramClient, bot_username: str, timeout: int):
    """
    Сброс состояния бота перед тестом.
    Отправляет /reset и подтверждает.
    """
    async with client.conversation(bot_username, timeout=timeout) as conv:
        await conv.send_message("/reset")
        response = await conv.get_response()

        # Ищем кнопку подтверждения
        if response.buttons:
            for row in response.buttons:
                for button in row:
                    if "сбросить" in button.text.lower():
                        await button.click()
                        await conv.get_response()
                        break

        # Небольшая пауза
        await asyncio.sleep(1)

    yield

    # После теста тоже сбрасываем
    async with client.conversation(bot_username, timeout=timeout) as conv:
        await conv.send_message("/reset")
        response = await conv.get_response()
        if response.buttons:
            for row in response.buttons:
                for button in row:
                    if "сбросить" in button.text.lower():
                        await button.click()
                        try:
                            await conv.get_response()
                        except:
                            pass
                        break
