#!/usr/bin/env python3
"""
Браузерное тестирование с ручным управлением
Браузер остается открытым до твоего указания
"""

import time
import os
import sys
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# Отключаем буферизацию вывода
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)

BOT_USERNAME = "training_dag_run_bot"
SCREENSHOTS_DIR = "/Users/noor/Documents/Obsidian Vault/Бот тренера/screenshots"

print("="*70, flush=True)
print("🌐 РУЧНОЕ БРАУЗЕРНОЕ ТЕСТИРОВАНИЕ БОТА", flush=True)
print("="*70, flush=True)
print(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
print(f"Браузер: Google Chrome", flush=True)
print(f"Бот: @{BOT_USERNAME}", flush=True)
print("="*70, flush=True)
print(flush=True)

os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

print("🚀 Запускаю Google Chrome...", flush=True)

# Настройки Chrome
chrome_options = Options()
chrome_options.binary_location = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
# БЕЗ headless - нужно видимое окно
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('--window-size=1400,900')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

print("✅ Chrome запущен!", flush=True)
print(flush=True)

# Открываем Telegram Web
print("📱 Открываю Telegram Web...", flush=True)
driver.get('https://web.telegram.org/k/')
time.sleep(3)

print(f"✅ Telegram Web открыт: {driver.current_url}", flush=True)
print(flush=True)

# Скриншот
screenshot_path = f'{SCREENSHOTS_DIR}/manual_test_01.png'
driver.save_screenshot(screenshot_path)
print(f"📸 Скриншот: {screenshot_path}", flush=True)
print(flush=True)

# Инструкции
print("="*70, flush=True)
print("💡 ИНСТРУКЦИЯ ПО ТЕСТИРОВАНИЮ", flush=True)
print("="*70, flush=True)
print(flush=True)
print("ШАГ 1: Авторизация", flush=True)
print("   • Отсканируй QR-код в открывшемся Chrome через Telegram на телефоне", flush=True)
print("   • Или нажми 'LOG IN BY PHONE NUMBER' и введи номер", flush=True)
print(flush=True)

print("ШАГ 2: Поиск бота", flush=True)
print(f"   • Нажми на иконку поиска (лупа вверху слева)", flush=True)
print(f"   • Введи: @{BOT_USERNAME}", flush=True)
print(f"   • Открой чат с ботом", flush=True)
print(flush=True)

print("ШАГ 3: Тестирование команд", flush=True)
print("   • Отправь /start", flush=True)
print("   • Проверь что появились 4 inline кнопки:", flush=True)
print("     - 📊 Статистика", flush=True)
print("     - 📅 План", flush=True)
print("     - 🔄 Синхронизация", flush=True)
print("     - 📲 Календарь", flush=True)
print(flush=True)

print("ШАГ 4: Проверка кнопок", flush=True)
print("   • Нажми каждую inline кнопку", flush=True)
print("   • Проверь что они работают", flush=True)
print(flush=True)

print("ШАГ 5: Проверка команд", flush=True)
print("   • /help - справка", flush=True)
print("   • /stats - статистика (если есть Garmin)", flush=True)
print("   • /plan - создание плана тренировок", flush=True)
print("   • /calendar - должен отправить ICS файл", flush=True)
print(flush=True)

print("ШАГ 6: Проверка форматирования", flush=True)
print("   • Сообщения должны быть с Markdown форматированием", flush=True)
print("   • Жирный текст, списки, заголовки", flush=True)
print(flush=True)

print("="*70, flush=True)
print("⚠️  ВАЖНО: Браузер останется открытым для тестирования", flush=True)
print("="*70, flush=True)
print(flush=True)

# Ждем
print("⏳ Браузер останется открытым...", flush=True)
print("   Тестируй бота в открывшемся окне Chrome", flush=True)
print("   Когда закончишь - нажми Ctrl+C в терминале или закрой окно браузера", flush=True)
print(flush=True)

try:
    # Бесконечный цикл пока не нажмут Ctrl+C
    while True:
        time.sleep(60)
        print(".", end="", flush=True)

except KeyboardInterrupt:
    print(flush=True)
    print(flush=True)
    print("="*70, flush=True)
    print("✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО", flush=True)
    print("="*70, flush=True)
    print(f"📸 Скриншоты сохранены в: {SCREENSHOTS_DIR}", flush=True)
    print("✅ Закрываю браузер...", flush=True)
    print("="*70, flush=True)

finally:
    try:
        driver.quit()
        print("✅ Браузер закрыт", flush=True)
    except:
        pass
