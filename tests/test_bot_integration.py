"""
Smoke тесты структуры проекта.

Запуск:
    pytest tests/test_bot_integration.py -v
"""

import pytest
from pathlib import Path


def test_src_structure():
    """Проверка структуры src/."""
    src = Path(__file__).parent.parent / "src"

    assert src.exists(), "Папка src/ не найдена"
    assert (src / "bot").exists(), "Папка src/bot/ не найдена"
    assert (src / "bot" / "telegram_bot.py").exists(), "telegram_bot.py не найден"


def test_handlers_exist():
    """Проверка что основные handlers определены."""
    bot_file = Path(__file__).parent.parent / "src" / "bot" / "telegram_bot.py"
    content = bot_file.read_text()

    # Проверяем наличие основных handlers (по актуальным названиям)
    assert "async def start" in content, "start handler не найден"
    assert "ask_garmin_email" in content or "garmin" in content.lower(), "Garmin handlers не найдены"
    assert "def _setup_handlers" in content, "_setup_handlers не найден"


def test_callback_patterns():
    """Проверка что callback patterns зарегистрированы."""
    bot_file = Path(__file__).parent.parent / "src" / "bot" / "telegram_bot.py"
    content = bot_file.read_text()

    # Проверяем паттерны
    assert "racetype_" in content, "Паттерн racetype_ не найден"
    assert "trainday_" in content, "Паттерн trainday_ не найден"
    assert "goal_" in content, "Паттерн goal_ не найден"


def test_dependencies():
    """Проверка что зависимости импортируются."""
    bot_file = Path(__file__).parent.parent / "src" / "bot" / "telegram_bot.py"
    content = bot_file.read_text()

    # Проверяем импорты
    assert "from telegram import" in content
    assert "from telegram.ext import" in content
    assert "InlineKeyboardButton" in content
    assert "InlineKeyboardMarkup" in content


def test_env_example_complete():
    """Проверка что .env.example содержит все нужные переменные."""
    env_example = Path(__file__).parent.parent / ".env.example"

    assert env_example.exists(), ".env.example не найден"

    content = env_example.read_text()

    required_vars = [
        "TELEGRAM_BOT_TOKEN",
        "GARMIN_EMAIL",
        "GARMIN_PASSWORD"
    ]

    for var in required_vars:
        assert var in content, f"{var} отсутствует в .env.example"


def test_readme_exists():
    """Проверка наличия README."""
    readme = Path(__file__).parent.parent / "README.md"
    assert readme.exists() or (Path(__file__).parent.parent.parent / "README.md").exists(), \
        "README.md не найден"


def test_requirements_has_telegram():
    """Проверка что requirements.txt содержит python-telegram-bot."""
    requirements = Path(__file__).parent.parent / "requirements.txt"

    assert requirements.exists(), "requirements.txt не найден"

    content = requirements.read_text()
    assert "python-telegram-bot" in content, "python-telegram-bot отсутствует"
    assert "telethon" in content, "telethon отсутствует (для будущих e2e)"
    assert "pytest" in content, "pytest отсутствует"


# Integration тесты требуют сложной настройки моков
# Вместо этого используем ручное тестирование по инструкции
# См. tests/MANUAL_TESTING.md
