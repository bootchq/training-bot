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
    ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "57186925"))

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

    # Strava
    STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
    STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
    STRAVA_REDIRECT_URI = os.getenv("STRAVA_REDIRECT_URI", "http://localhost:8080/callback")

    # AI API
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")  # Бесплатный (рекомендуется)
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL")  # PostgreSQL URL (приоритет)
    DATABASE_PATH = os.getenv("DATABASE_PATH") if not DATABASE_URL else None

    # Fallback для SQLite если нет ни DATABASE_URL ни DATABASE_PATH
    if not DATABASE_URL and not DATABASE_PATH:
        DATABASE_PATH = str(DATA_DIR / "training_bot.db")

    # Timezone
    TIMEZONE = os.getenv("TZ", "Europe/Moscow")

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = LOGS_DIR / "bot.log"

    # Расписание
    SYNC_TIME = "19:00"  # Время ежедневной синхронизации Garmin

    # Garmin token persistence
    # Автодетект: если Railway Volume смонтирован на /data — используем его.
    # Иначе — локальная папка data/garth_tokens/ (не персистентна на Railway без Volume).
    _garth_default = "/data/garth_tokens" if os.path.isdir("/data") else str(DATA_DIR / "garth_tokens")
    GARTH_HOME = os.getenv("GARTH_HOME", _garth_default)

    # Webhook (для Railway деплоя)
    # Если задан WEBHOOK_URL — бот использует webhook вместо polling
    # Пример: https://training-bot-production.up.railway.app
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

    @classmethod
    def validate(cls):
        """Проверка обязательных переменных"""
        required = [
            ("TELEGRAM_BOT_TOKEN", cls.TELEGRAM_BOT_TOKEN),
        ]

        missing = [name for name, value in required if not value]

        if missing:
            raise ValueError(
                f"Отсутствуют обязательные переменные окружения: {', '.join(missing)}"
            )

        # Проверка трекеров (хотя бы один)
        if not (cls.GARMIN_EMAIL or cls.STRAVA_CLIENT_ID):
            print("⚠️  Предупреждение: Не настроен ни Garmin, ни Strava")
            print("   Настрой учётные данные в .env")

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
