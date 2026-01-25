#!/usr/bin/env python3
"""
Генератор StringSession для Telethon.
Запустить ОДИН раз для создания сессии без SMS каждый раз.

Использование:
    python scripts/generate_telethon_session.py API_ID API_HASH

После запуска:
1. Введи номер телефона
2. Введи код из Telegram
3. Скопируй StringSession в .env.e2e файл
"""

import asyncio
import os
import sys

try:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
except ImportError:
    print("Установи telethon: pip install telethon")
    sys.exit(1)


async def main():
    print("=" * 60)
    print("ГЕНЕРАТОР TELETHON SESSION")
    print("=" * 60)
    print()

    # Получаем API_ID и API_HASH из аргументов или env
    api_id = None
    api_hash = None

    if len(sys.argv) >= 3:
        api_id = int(sys.argv[1])
        api_hash = sys.argv[2]
    else:
        api_id = os.getenv("TELEGRAM_API_ID")
        api_hash = os.getenv("TELEGRAM_API_HASH")

        if api_id:
            api_id = int(api_id)

    if not api_id or not api_hash:
        print("Использование:")
        print("  python scripts/generate_telethon_session.py API_ID API_HASH")
        print()
        print("Или установи переменные окружения:")
        print("  export TELEGRAM_API_ID=12345")
        print("  export TELEGRAM_API_HASH=abc123...")
        print()
        print("Получить на https://my.telegram.org -> API Development Tools")
        sys.exit(1)

    print(f"API_ID: {api_id}")
    print(f"API_HASH: {api_hash[:8]}...")
    print()
    print("Создаю клиент...")
    print("Введи номер телефона и код из Telegram...")
    print()

    # Создаем клиент с пустой StringSession
    client = TelegramClient(StringSession(), api_id, api_hash)

    await client.start()

    # Получаем StringSession
    session_string = client.session.save()

    print()
    print("=" * 60)
    print("СЕССИЯ СОЗДАНА!")
    print("=" * 60)
    print()
    print("Добавь эту строку в .env.e2e:")
    print()
    print(f'TELETHON_SESSION="{session_string}"')
    print()
    print("=" * 60)

    # Проверяем что сессия работает
    me = await client.get_me()
    print(f"Авторизован как: {me.first_name} (@{me.username})")
    print()

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
