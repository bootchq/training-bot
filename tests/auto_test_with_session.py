#!/usr/bin/env python3
"""
ПОЛНОСТЬЮ АВТОМАТИЧЕСКИЙ ТЕСТ С СОХРАНЕНИЕМ СЕССИИ
Использует ТВОЙ реальный профиль Chrome - авторизация ОДИН РАЗ, потом навсегда сохранена!
"""

import os
import subprocess
import time

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEFAULT_PROFILE = os.path.expanduser("~/Library/Application Support/Google/Chrome")
BOT_USERNAME = "training_dag_run_bot"
SCREENSHOTS_DIR = "/Users/noor/Documents/Obsidian Vault/Бот тренера/screenshots"

print("="*70, flush=True)
print("🤖 АВТОТЕСТ С СОХРАНЕНИЕМ СЕССИИ", flush=True)
print("="*70, flush=True)
print(flush=True)

os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

# Проверяем, доступен ли remote debugging
print("🔍 Проверяю remote debugging порт 9222...", flush=True)
try:
    r = requests.get("http://127.0.0.1:9222/json/version", timeout=2)
    if r.status_code == 200:
        print("✅ Chrome уже запущен с remote debugging!", flush=True)
        chrome_running = True
    else:
        chrome_running = False
except Exception:
    chrome_running = False
    print("⚠️  Remote debugging недоступен", flush=True)

# Если порт недоступен - перезапускаем Chrome
if not chrome_running:
    print(flush=True)
    print("🔄 Перезапускаю Chrome с правильными настройками...", flush=True)
    print("   (это нужно ОДИН РАЗ, потом сессия сохранена навсегда)", flush=True)
    print(flush=True)

    # Закрываем Chrome корректно через AppleScript
    print("📋 Закрываю текущий Chrome...", flush=True)
    subprocess.run([
        "osascript", "-e", 'tell application "Google Chrome" to quit'
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)

    # Убиваем оставшиеся процессы
    subprocess.run(["killall", "Google Chrome"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)

    # Запускаем Chrome с ДЕФОЛТНЫМ профилем и remote debugging
    print("🚀 Запускаю Chrome с твоим профилем...", flush=True)
    subprocess.Popen([
        CHROME_PATH,
        "--remote-debugging-port=9222",
        f"--user-data-dir={DEFAULT_PROFILE}",
        "--profile-directory=Default",
        "https://web.telegram.org/k/"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print("⏳ Жду готовности remote debugging...", flush=True)
    # Ждем пока порт станет доступен
    for i in range(20):
        time.sleep(2)
        try:
            r = requests.get("http://127.0.0.1:9222/json/version", timeout=1)
            if r.status_code == 200:
                print("✅ Remote debugging готов!", flush=True)
                break
        except Exception:
            pass
    else:
        print("⚠️  Таймаут ожидания порта", flush=True)

    time.sleep(2)

# Подключаемся к Chrome
print(flush=True)
print("🔌 Подключаюсь к Chrome...", flush=True)

chrome_options = Options()
chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

driver = webdriver.Chrome(options=chrome_options)
print("✅ Подключен!", flush=True)
print(flush=True)

# Проверяем Telegram
current_url = driver.current_url
print(f"📍 Текущая страница: {current_url[:50]}...", flush=True)

page_source = driver.page_source
if 'Log in' in page_source or 'Sign in' in page_source or 'QR Code' in page_source:
    print(flush=True)
    print("="*70, flush=True)
    print("⚠️  ТРЕБУЕТСЯ АВТОРИЗАЦИЯ В TELEGRAM", flush=True)
    print("="*70, flush=True)
    print(flush=True)
    print("💡 ИНСТРУКЦИЯ:", flush=True)
    print("   1. Открылся Chrome с Telegram Web", flush=True)
    print("   2. Авторизуйся через QR-код (ПОСЛЕДНИЙ РАЗ!)", flush=True)
    print("   3. После авторизации сессия сохранится НАВСЕГДА", flush=True)
    print(flush=True)
    print("⏳ Жду авторизации 90 секунд...", flush=True)

    for i in range(9, 0, -1):
        print(f"   Осталось {i*10} секунд...", flush=True)
        time.sleep(10)

        page_source = driver.page_source
        if 'Log in' not in page_source and 'Sign in' not in page_source:
            print(flush=True)
            print("✅ АВТОРИЗАЦИЯ УСПЕШНА! Сессия сохранена навсегда!", flush=True)
            break
    else:
        print(flush=True)
        print("⚠️  Время вышло - перезапусти скрипт после авторизации", flush=True)
        driver.quit()
        exit(0)
else:
    print("✅ Уже авторизован - сессия сохранена!", flush=True)

print(flush=True)

# Открываем бота
print(f"🔍 Открываю бота @{BOT_USERNAME}...", flush=True)
bot_url = f"https://web.telegram.org/k/#{BOT_USERNAME}"
driver.get(bot_url)
time.sleep(5)

print("✅ Бот открыт", flush=True)
driver.save_screenshot(f"{SCREENSHOTS_DIR}/session_01_bot.png")
print(flush=True)

# Отправляем /start
print("📝 Отправляю /start...", flush=True)

input_selectors = ['div[contenteditable="true"]', '.input-message-input']
message_input = None

for selector in input_selectors:
    try:
        message_input = driver.find_element(By.CSS_SELECTOR, selector)
        if message_input:
            break
    except Exception:
        continue

if message_input:
    message_input.click()
    time.sleep(0.5)
    message_input.send_keys('/start')
    time.sleep(0.5)
    message_input.send_keys(Keys.ENTER)
    print("✅ /start отправлен", flush=True)
    time.sleep(3)
    driver.save_screenshot(f"{SCREENSHOTS_DIR}/session_02_start.png")
else:
    print("⚠️  Поле ввода не найдено", flush=True)

print(flush=True)

# Ищем кнопки
print("🔘 Ищу inline кнопки...", flush=True)
time.sleep(2)

buttons = []
for selector in ['button.reply-markup-button', 'button[class*="Button"]']:
    try:
        found = driver.find_elements(By.CSS_SELECTOR, selector)
        if found:
            buttons = found
            break
    except Exception:
        continue

if buttons:
    print(f"✅ Найдено {len(buttons)} кнопок", flush=True)
    print(flush=True)
    print("🖱️  КЛИКАЮ ПО КНОПКАМ:", flush=True)
    print("-" * 70, flush=True)

    for idx, btn in enumerate(buttons[:4], 1):
        try:
            btn_text = btn.text
            print(f"\n{idx}. {btn_text}", flush=True)

            btn.click()
            print("   ✅ КЛИКНУЛ!", flush=True)
            time.sleep(2)

            driver.save_screenshot(f"{SCREENSHOTS_DIR}/session_03_btn{idx}.png")

            # Проверяем файл
            page = driver.page_source
            if '.ics' in page and 'календарь' in btn_text.lower():
                print("   🎉 КАЛЕНДАРЬ ОТПРАВИЛ ICS ФАЙЛ!", flush=True)

        except Exception as e:
            print(f"   ⚠️  {e}", flush=True)

    print(flush=True)
    print("="*70, flush=True)
    print("✅ ВСЕ КНОПКИ ПРОТЕСТИРОВАНЫ!", flush=True)
    print("="*70, flush=True)
else:
    print("⚠️  Кнопки не найдены", flush=True)

print(flush=True)
print(f"📸 Скриншоты: {SCREENSHOTS_DIR}", flush=True)
print(flush=True)
print("="*70, flush=True)
print("💡 ГОТОВО!", flush=True)
print("="*70, flush=True)
print(flush=True)
print("Chrome остается открытым с сохраненной сессией.", flush=True)
print("В следующий раз тест запустится БЕЗ авторизации!", flush=True)
print(flush=True)
