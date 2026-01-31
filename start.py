#!/usr/bin/env python3
"""
Wrapper для запуска разных сервисов в Railway

Использует переменную окружения SERVICE_NAME:
- SERVICE_NAME=bot → запускает main_bot.py (Service 1)
- SERVICE_NAME=background → запускает main_background.py (Service 2)
"""
import os
import sys

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
