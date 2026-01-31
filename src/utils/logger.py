"""Настройка логирования"""
import logging
import sys
from logging.handlers import RotatingFileHandler

from .config import Config


def setup_logger(name: str = "bot_trainer") -> logging.Logger:
    """
    Настройка логгера с выводом в файл и консоль

    Args:
        name: Имя логгера

    Returns:
        Настроенный логгер
    """
    logger = logging.getLogger(name)
    logger.setLevel(Config.LOG_LEVEL)

    # Избегаем дублирования хендлеров
    if logger.handlers:
        return logger

    # Формат логов
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Хендлер для файла (ротация при 10 МБ, хранить 5 файлов)
    file_handler = RotatingFileHandler(
        Config.LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10 МБ
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(Config.LOG_LEVEL)
    file_handler.setFormatter(formatter)

    # Хендлер для консоли
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(Config.LOG_LEVEL)
    console_handler.setFormatter(formatter)

    # Добавление хендлеров
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# Создание глобального логгера
logger = setup_logger()
