#!/usr/bin/env python3
"""
Скрипт для локальной OAuth авторизации Google Calendar

Запуск:
    python -m bot_trainer.scripts.google_auth

После авторизации скопируй refresh_token и введи в боте:
    /set_google_token <refresh_token>
"""
import os
import sys

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/calendar.events']


def main():
    """Локальная авторизация Google"""
    credentials_path = os.environ.get('GOOGLE_CREDENTIALS_PATH')

    if not credentials_path:
        # Ищем credentials.json в текущей папке или выше
        possible_paths = [
            'credentials.json',
            '../credentials.json',
            '../../credentials.json',
            os.path.expanduser('~/credentials.json'),
        ]
        for path in possible_paths:
            if os.path.exists(path):
                credentials_path = path
                break

    if not credentials_path or not os.path.exists(credentials_path):
        print("❌ Файл credentials.json не найден!")
        print("\nИнструкция:")
        print("1. Перейди на https://console.cloud.google.com/apis/credentials")
        print("2. Создай OAuth 2.0 Client ID (Desktop app)")
        print("3. Скачай JSON и сохрани как credentials.json")
        print("4. Запусти этот скрипт снова")
        return

    print("🔐 Запуск авторизации Google Calendar...")
    print("   Откроется браузер для входа в Google аккаунт\n")

    try:
        flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
        creds = flow.run_local_server(port=8080)

        print("\n" + "=" * 50)
        print("✅ АВТОРИЗАЦИЯ УСПЕШНА!")
        print("=" * 50)
        print("\n📋 Твой refresh_token:")
        print("-" * 50)
        print(creds.refresh_token)
        print("-" * 50)
        print("\n📲 Скопируй токен и отправь боту команду:")
        print(f"   /set_google_token {creds.refresh_token[:20]}...")
        print("\n⚠️  Храни токен в секрете! Он даёт доступ к твоему календарю.")

    except Exception as e:
        print(f"\n❌ Ошибка авторизации: {e}")


if __name__ == '__main__':
    main()
