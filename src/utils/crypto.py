"""Шифрование чувствительных данных (Fernet)"""
import base64
import os

from cryptography.fernet import Fernet

from .logger import logger


def _get_key() -> bytes:
    """Получить ключ шифрования из env или сгенерировать"""
    key = os.getenv("ENCRYPTION_KEY")
    if key:
        return key.encode()

    # Если ключа нет — генерируем из TELEGRAM_BOT_TOKEN (детерминированный)
    # Это позволяет работать без отдельного env var
    token = os.getenv("TELEGRAM_BOT_TOKEN", "default-key-for-dev")
    # Fernet требует 32 байта base64-encoded
    raw = token.encode()[:32].ljust(32, b'\0')
    return base64.urlsafe_b64encode(raw)


_fernet = None


def _get_fernet() -> Fernet:
    """Ленивая инициализация Fernet"""
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_get_key())
    return _fernet


def encrypt(plaintext: str) -> str:
    """Зашифровать строку, вернуть base64"""
    if not plaintext:
        return plaintext
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Расшифровать строку"""
    if not ciphertext:
        return ciphertext
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except Exception:
        # Если не удалось расшифровать — вероятно plain text (до миграции)
        logger.debug("Не удалось расшифровать, возвращаю как есть (plain text)")
        return ciphertext
