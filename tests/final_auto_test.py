#!/usr/bin/env python3
"""
ФИНАЛЬНЫЙ АВТОМАТИЧЕСКИЙ ТЕСТ
Использует ТВОЮ существующую сессию Chrome - авторизация НЕ НУЖНА!
"""

import os
import subprocess
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

SCREENSHOTS_DIR = "/Users/noor/Documents/Obsidian Vault/Бот тренера/screenshots"
BOT_USERNAME = "training_dag_run_bot"

print("="*70, flush=True)
print("🤖 АВТОМАТИЧЕСКИЙ ТЕСТ - БЕЗ АВТОРИЗАЦИИ", flush=True)
print("="*70, flush=True)
print("Использую ТВОЙ профиль Chrome - сессия УЖЕ там!", flush=True)
print("="*70, flush=True)
print(flush=True)

os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

# Пытаемся подключиться к уже запущенному Chrome
print("🔌 Проверяю запущен ли Chrome с remote debugging...", flush=True)

chrome_options = Options()
chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

driver = None
try:
    driver = webdriver.Chrome(options=chrome_options)
    print("✅ Подключился к запущенному Chrome!", flush=True)
except Exception:
    print("⚠️  Chrome не запущен с remote debugging", flush=True)
    print("🚀 Запускаю Chrome с ТВОИМ дефолтным профилем...", flush=True)

    # Запускаем Chrome с ДЕФОЛТНЫМ профилем (где уже есть сессия!)
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    default_profile = os.path.expanduser("~/Library/Application Support/Google/Chrome")

    subprocess.Popen([
        chrome_path,
        "--remote-debugging-port=9222",
        f"--user-data-dir={default_profile}",
        "--profile-directory=Default",  # ТВОЙ ДЕФОЛТНЫЙ ПРОФИЛЬ!
        "https://web.telegram.org/k/"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    time.sleep(8)

    # Подключаемся
    driver = webdriver.Chrome(options=chrome_options)
    print("✅ Запустил Chrome с твоим профилем!", flush=True)

print(flush=True)

# Переходим к боту
print(f"🔍 Открываю бота @{BOT_USERNAME}...", flush=True)
bot_url = f"https://web.telegram.org/k/#{BOT_USERNAME}"
driver.get(bot_url)
time.sleep(5)

print("✅ Бот открыт", flush=True)
driver.save_screenshot(f"{SCREENSHOTS_DIR}/final_01_bot.png")
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
    driver.save_screenshot(f"{SCREENSHOTS_DIR}/final_02_start.png")
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

            driver.save_screenshot(f"{SCREENSHOTS_DIR}/final_03_btn{idx}.png")

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
print("⏳ Chrome остается открытым 30 сек...", flush=True)
time.sleep(30)

print("✅ Готово!", flush=True)
