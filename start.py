#!/usr/bin/env python3
"""
Wrapper для запуска разных сервисов в Railway

Использует переменную окружения SERVICE_NAME:
- SERVICE_NAME=bot → запускает main_bot.py (Service 1)
- SERVICE_NAME=background → запускает main_background.py (Service 2)
- RUN_MIGRATION=true → запускает миграцию SQLite → PostgreSQL
"""
import os
import sys

# Проверка на одноразовую миграцию
if os.getenv('RUN_MIGRATION') == 'true':
    print("🔄 Запуск миграции SQLite → PostgreSQL...")
    import migrate_sqlite_to_postgres
    success = migrate_sqlite_to_postgres.migrate_data()
    sys.exit(0 if success else 1)

SERVICE_NAME = os.getenv('SERVICE_NAME', 'bot')

if SERVICE_NAME == 'bot':
    print("🚀 Запуск Service 1: Коммуникация с пользователем")
    import main_bot
    main_bot.main()
elif SERVICE_NAME == 'background':
    print("🚀 Запуск Service 2: Фоновая логика и анализ")
    import main_background
    main_background.main()
else:
    print(f"❌ Неизвестный SERVICE_NAME: {SERVICE_NAME}")
    print("Допустимые значения: bot, background")
    sys.exit(1)
