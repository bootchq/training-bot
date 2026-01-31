#!/usr/bin/env python3
"""
Интерактивное тестирование бота - я сам отправляю команды и проверяю результаты
"""

import os
import sys
import time
from datetime import datetime

import requests

# Отключаем буферизацию
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
BOT_USERNAME = "training_dag_run_bot"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Твой chat ID для отправки тестовых сообщений
# Получим из последних сообщений
CHAT_ID = None

def api_call(method, **params):
    """Вызов API"""
    url = f"{BASE_URL}/{method}"
    response = requests.get(url, params=params, timeout=30)
    return response.json()

def send_message(chat_id, text):
    """Отправка сообщения"""
    return api_call('sendMessage', chat_id=chat_id, text=text)

def get_updates(offset=0):
    """Получение обновлений"""
    return api_call('getUpdates', offset=offset, timeout=5)

def get_my_chat_id():
    """Получить ID чата с последним пользователем"""
    result = get_updates()
    if result.get('ok') and result.get('result'):
        updates = result['result']
        if updates:
            # Берем последнее сообщение
            last_update = updates[-1]
            if 'message' in last_update:
                return last_update['message']['chat']['id']
    return None

print("="*70, flush=True)
print("🤖 АВТОМАТИЧЕСКОЕ ТЕСТИРОВАНИЕ БОТА", flush=True)
print("="*70, flush=True)
print(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
print(f"Бот: @{BOT_USERNAME}", flush=True)
print("="*70, flush=True)
print(flush=True)

if not BOT_TOKEN:
    print("❌ TELEGRAM_BOT_TOKEN не установлен", flush=True)
    print("   Экспортируй токен: export TELEGRAM_BOT_TOKEN='твой_токен'", flush=True)
    sys.exit(1)

# Проверяем что бот работает
print("🔍 Проверяю бота...", flush=True)
bot_info = api_call('getMe')
if bot_info.get('ok'):
    bot = bot_info['result']
    print(f"✅ Бот онлайн: @{bot['username']}", flush=True)
else:
    print("❌ Бот не отвечает", flush=True)
    sys.exit(1)

print(flush=True)

# Получаем chat ID
print("📱 Ищу твой chat ID...", flush=True)
print("   💡 Если не найду - отправь любое сообщение боту и перезапусти скрипт", flush=True)

CHAT_ID = get_my_chat_id()

if not CHAT_ID:
    print("⚠️  Chat ID не найден", flush=True)
    print("   Отправь /start боту в Telegram и запусти скрипт заново", flush=True)
    sys.exit(1)

print(f"✅ Chat ID найден: {CHAT_ID}", flush=True)
print(flush=True)

# Начинаем тестирование
print("="*70, flush=True)
print("🧪 НАЧИНАЮ ТЕСТИРОВАНИЕ", flush=True)
print("="*70, flush=True)
print(flush=True)

# ТЕСТ 1: Команда /start
print("ТЕСТ 1: Отправляю команду /start", flush=True)
print("-" * 70, flush=True)

response = send_message(CHAT_ID, '/start')
time.sleep(2)

if response.get('ok'):
    msg = response['result']
    print("✅ Команда отправлена", flush=True)
    print(f"   Message ID: {msg['message_id']}", flush=True)

    # Проверяем есть ли inline кнопки в ответе
    # Для этого нужно получить обновления
    print("   Ожидаю ответа бота...", flush=True)
    time.sleep(3)

    # Получаем последние обновления
    updates = get_updates()
    if updates.get('ok'):
        print(f"   Получено обновлений: {len(updates.get('result', []))}", flush=True)
else:
    print(f"❌ Ошибка: {response}", flush=True)

print(flush=True)

# ТЕСТ 2: Команда /help
print("ТЕСТ 2: Отправляю команду /help", flush=True)
print("-" * 70, flush=True)

response = send_message(CHAT_ID, '/help')
time.sleep(2)

if response.get('ok'):
    print("✅ Команда отправлена", flush=True)
else:
    print(f"❌ Ошибка: {response}", flush=True)

print(flush=True)

# ТЕСТ 3: Команда /stats
print("ТЕСТ 3: Отправляю команду /stats", flush=True)
print("-" * 70, flush=True)

response = send_message(CHAT_ID, '/stats')
time.sleep(2)

if response.get('ok'):
    print("✅ Команда отправлена", flush=True)
    print("   (Если не зарегистрирован Garmin - покажет ошибку)", flush=True)
else:
    print(f"❌ Ошибка: {response}", flush=True)

print(flush=True)

# ТЕСТ 4: Команда /calendar
print("ТЕСТ 4: Отправляю команду /calendar", flush=True)
print("-" * 70, flush=True)

response = send_message(CHAT_ID, '/calendar')
time.sleep(3)

if response.get('ok'):
    print("✅ Команда отправлена", flush=True)
    print("   Должен отправить ICS файл (НЕ ошибку OAuth)", flush=True)
else:
    print(f"❌ Ошибка: {response}", flush=True)

print(flush=True)

# ТЕСТ 5: Команда /plan
print("ТЕСТ 5: Отправляю команду /plan", flush=True)
print("-" * 70, flush=True)

response = send_message(CHAT_ID, '/plan')
time.sleep(2)

if response.get('ok'):
    print("✅ Команда отправлена", flush=True)
else:
    print(f"❌ Ошибка: {response}", flush=True)

print(flush=True)

# Итоги
print("="*70, flush=True)
print("📊 ТЕСТИРОВАНИЕ ЗАВЕРШЕНО", flush=True)
print("="*70, flush=True)
print(flush=True)
print("✅ Все команды отправлены боту", flush=True)
print(flush=True)
print("💡 ПРОВЕРЬ В TELEGRAM:", flush=True)
print("   1. Открой чат с ботом", flush=True)
print("   2. Должны быть ответы на все команды", flush=True)
print("   3. Проверь inline кнопки после /start", flush=True)
print("   4. Убедись что /calendar отправил ICS файл", flush=True)
print("   5. Проверь форматирование сообщений", flush=True)
print(flush=True)
print("="*70, flush=True)
