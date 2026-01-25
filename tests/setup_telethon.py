#!/usr/bin/env python3
"""
НАСТРОЙКА TELETHON ДЛЯ E2E ТЕСТИРОВАНИЯ

Этот скрипт поможет получить и сохранить Telegram API credentials
для полного тестирования бота с кликами по inline кнопкам.

Запуск:
    python3 setup_telethon.py
"""

import os
from pathlib import Path

CONFIG_FILE = Path.home() / '.telegram_api_config'
SESSION_FILE = Path(__file__).parent.parent.parent / 'telegram_test_session'

def main():
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║              НАСТРОЙКА TELETHON ДЛЯ E2E ТЕСТИРОВАНИЯ                 ║
╚══════════════════════════════════════════════════════════════════════╝

📱 ШАГ 1: Получи API credentials

   1. Открой в браузере: https://my.telegram.org/apps
   2. Войди через свой номер телефона (придёт код в Telegram)
   3. Создай приложение:
      - App title: Bot Tester (любое)
      - Short name: bottester (любое)
      - Platform: Desktop
   4. Скопируй:
      - API ID (числовой)
      - API Hash (строка)
""")

    # Проверяем существующие credentials
    if CONFIG_FILE.exists():
        print(f"⚠️  Найдены сохранённые credentials в {CONFIG_FILE}")
        resp = input("Перезаписать? (y/n): ").strip().lower()
        if resp != 'y':
            print("Отменено.")
            return

    print("\n📝 ШАГ 2: Введи данные\n")

    try:
        api_id = input("API ID: ").strip()
        if not api_id.isdigit():
            print("❌ API ID должен быть числом")
            return

        api_hash = input("API Hash: ").strip()
        if len(api_hash) < 20:
            print("❌ API Hash слишком короткий")
            return

        phone = input("Номер телефона (с +7 или +375): ").strip()
        if not phone.startswith('+'):
            print("❌ Номер должен начинаться с +")
            return

        # Сохраняем
        with open(CONFIG_FILE, 'w') as f:
            f.write(f"{api_id}\n{api_hash}\n{phone}\n")

        print(f"""
✅ Credentials сохранены в {CONFIG_FILE}

📱 ШАГ 3: Авторизация в Telegram

   При первом запуске теста Telethon попросит:
   1. Код из SMS/Telegram (придёт на телефон)
   2. Пароль 2FA (если включён)

   Сессия сохранится в: {SESSION_FILE}
   После этого авторизация больше не потребуется.

🚀 ШАГ 4: Запусти полный тест

   cd tests
   python3 bot_tester.py --full

   Или напрямую:
   python3 bot_tester.py --full
""")

    except KeyboardInterrupt:
        print("\n\n❌ Отменено")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")


if __name__ == "__main__":
    main()
