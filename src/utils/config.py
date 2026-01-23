"""Конфигурация приложения"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

class Config:
    """Настройки приложения"""

    # Пути
    BASE_DIR = Path(__file__).parent.parent.parent
    DATA_DIR = BASE_DIR / "data"
    CONFIG_DIR = BASE_DIR / "config"
    LOGS_DIR = BASE_DIR / "logs"

    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

    # Garmin
    GARMIN_EMAIL = os.getenv("GARMIN_EMAIL")
    GARMIN_PASSWORD = os.getenv("GARMIN_PASSWORD")

    # Google Calendar
    GOOGLE_CREDENTIALS_PATH = os.getenv(
        "GOOGLE_CREDENTIALS_PATH",
        str(CONFIG_DIR / "credentials.json")
    )
    GOOGLE_TOKEN_PATH = os.getenv(
        "GOOGLE_TOKEN_PATH",
        str(CONFIG_DIR / "token.json")
    )

    # AI API
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")  # Бесплатный (рекомендуется)
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    # Database
    DATABASE_PATH = os.getenv(
        "DATABASE_PATH",
        str(DATA_DIR / "training_bot.db")
    )

    # Timezone
    TIMEZONE = os.getenv("TZ", "Europe/Moscow")

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = LOGS_DIR / "bot.log"

    # Расписание
    SYNC_TIME = "19:00"  # Время ежедневной синхронизации Garmin

    @classmethod
    def validate(cls):
        """Проверка обязательных переменных"""
        required = [
            ("TELEGRAM_BOT_TOKEN", cls.TELEGRAM_BOT_TOKEN),
            ("GARMIN_EMAIL", cls.GARMIN_EMAIL),
            ("GARMIN_PASSWORD", cls.GARMIN_PASSWORD),
        ]

        missing = [name for name, value in required if not value]

        if missing:
            raise ValueError(
                f"Отсутствуют обязательные переменные окружения: {', '.join(missing)}"
            )

        # Проверка AI API (хотя бы один)
        if not cls.GROQ_API_KEY and not cls.ANTHROPIC_API_KEY and not cls.OPENAI_API_KEY:
            print("⚠️  Предупреждение: Не указан API-ключ для AI (Groq/Claude/OpenAI)")
            print("   Получи бесплатный ключ Groq: https://console.groq.com")

        # Создание папок
        cls.DATA_DIR.mkdir(exist_ok=True)
        cls.CONFIG_DIR.mkdir(exist_ok=True)
        cls.LOGS_DIR.mkdir(exist_ok=True)


# Валидация при импорте
Config.validate()
