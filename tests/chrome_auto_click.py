#!/usr/bin/env python3
"""
ПОЛНОСТЬЮ АВТОМАТИЧЕСКИЙ БРАУЗЕРНЫЙ ТЕСТ
Запускает Chrome, подключается, АВТОМАТИЧЕСКИ кликает по кнопкам
"""

import os
import subprocess
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
TELEGRAM_WEB = "https://web.telegram.org/k/"
BOT_USERNAME = "training_dag_run_bot"
SCREENSHOTS_DIR = "/Users/noor/Documents/Obsidian Vault/Бот тренера/screenshots"
# Используем ДЕФОЛТНЫЙ профиль Chrome - там уже есть твоя авторизация!
USER_DATA_DIR = os.path.expanduser("~/Library/Application Support/Google/Chrome")

print("="*70, flush=True)
print("🤖 АВТОМАТИЧЕСКИЙ БРАУЗЕРНЫЙ ТЕСТ", flush=True)
print("="*70, flush=True)
print(flush=True)

os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
os.makedirs(USER_DATA_DIR, exist_ok=True)

# Запускаем Chrome
print("🚀 Запускаю Chrome...", flush=True)
chrome_process = subprocess.Popen([
    CHROME_PATH,
    "--remote-debugging-port=9222",
    f"--user-data-dir={USER_DATA_DIR}",
    "--no-first-run",
    TELEGRAM_WEB
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

print("✅ Chrome запущен", flush=True)
time.sleep(5)

# Подключаемся
print("🔌 Подключаюсь к Chrome...", flush=True)
chrome_options = Options()
chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

try:
    driver = webdriver.Chrome(options=chrome_options)
    print("✅ Подключен!", flush=True)
    print(flush=True)

    # Проверяем авторизацию
    print("🔍 Проверяю Telegram Web...", flush=True)
    time.sleep(3)

    page_source = driver.page_source
    driver.save_screenshot(f"{SCREENSHOTS_DIR}/auto_01_initial.png")

    if 'Log in' in page_source or 'Sign in' in page_source:
        print("⚠️  Требуется авторизация", flush=True)
        print(flush=True)
        print("💡 ИНСТРУКЦИЯ:", flush=True)
        print("   1. Открыт Chrome с Telegram Web", flush=True)
        print("   2. Авторизуйся через QR-код или номер телефона", flush=True)
        print("   3. После авторизации перезапусти этот скрипт", flush=True)
        print(flush=True)
        print("   Chrome остается открытым на 60 секунд для авторизации...", flush=True)

        # Ждем 60 секунд
        for i in range(60, 0, -10):
            print(f"   Осталось {i} секунд...", flush=True)
            time.sleep(10)

        # Проверяем снова
        page_source = driver.page_source
        if 'Log in' not in page_source and 'Sign in' not in page_source:
            print("✅ Авторизация успешна!", flush=True)
        else:
            print("⚠️  Авторизация не завершена - перезапусти скрипт после авторизации", flush=True)
            driver.quit()
            chrome_process.terminate()
            exit(0)

    else:
        print("✅ Уже авторизован!", flush=True)

    print(flush=True)

    # Ищем бота автоматически
    print("🔍 Ищу бота автоматически...", flush=True)

    # Пытаемся открыть бота через deep link
    bot_url = f"https://web.telegram.org/k/#{BOT_USERNAME}"
    driver.get(bot_url)
    time.sleep(5)

    print(f"✅ Открыл чат с @{BOT_USERNAME}", flush=True)
    driver.save_screenshot(f"{SCREENSHOTS_DIR}/auto_02_bot_opened.png")
    print(flush=True)

    # Отправляем /start
    print("📝 Отправляю /start...", flush=True)

    input_selectors = [
        'div[contenteditable="true"]',
        '.input-message-input'
    ]

    message_input = None
    for selector in input_selectors:
        try:
            message_input = driver.find_element(By.CSS_SELECTOR, selector)
            if message_input:
                break
        except:
            continue

    if message_input:
        message_input.click()
        time.sleep(0.5)
        message_input.send_keys('/start')
        time.sleep(0.5)
        message_input.send_keys(Keys.ENTER)

        print("✅ /start отправлен", flush=True)
        time.sleep(3)

        driver.save_screenshot(f"{SCREENSHOTS_DIR}/auto_03_start_sent.png")
    else:
        print("⚠️  Не могу найти поле ввода", flush=True)

    print(flush=True)

    # Ищем кнопки
    print("🔘 Ищу inline кнопки...", flush=True)
    time.sleep(2)

    button_selectors = [
        'button.reply-markup-button',
        'button[class*="Button"]',
        'button[class*="keyboard"]'
    ]

    buttons = []
    for selector in button_selectors:
        try:
            found = driver.find_elements(By.CSS_SELECTOR, selector)
            if found:
                buttons = found
                print(f"✅ Найдено {len(buttons)} кнопок", flush=True)
                break
        except:
            continue

    if buttons:
        print(flush=True)
        print("🖱️  КЛИКАЮ ПО КНОПКАМ:", flush=True)
        print("-" * 70, flush=True)

        for idx, btn in enumerate(buttons[:4], 1):
            try:
                btn_text = btn.text
                print(f"\n{idx}. {btn_text}", flush=True)

                btn.click()
                print("   ✅ КЛИКНУЛ", flush=True)

                time.sleep(2)
                driver.save_screenshot(f"{SCREENSHOTS_DIR}/auto_04_button_{idx}.png")

            except Exception as e:
                print(f"   ⚠️  Ошибка: {e}", flush=True)

    else:
        print("⚠️  Кнопки не найдены", flush=True)

    print(flush=True)

    # Тестируем команды
    commands = ['/help', '/calendar']

    for cmd in commands:
        print(f"📝 Отправляю {cmd}...", flush=True)

        if message_input:
            message_input.click()
            time.sleep(0.3)
            message_input.send_keys(cmd)
            time.sleep(0.3)
            message_input.send_keys(Keys.ENTER)
            time.sleep(3)
            print("   ✅ Отправлен", flush=True)

    print(flush=True)

    # Итоги
    print("="*70, flush=True)
    print("✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО", flush=True)
    print("="*70, flush=True)
    print(flush=True)
    print("📸 Скриншоты:", SCREENSHOTS_DIR, flush=True)
    print("   auto_01_initial.png - начало", flush=True)
    print("   auto_02_bot_opened.png - бот открыт", flush=True)
    print("   auto_03_start_sent.png - /start отправлен", flush=True)
    print("   auto_04_button_X.png - кнопки", flush=True)
    print(flush=True)
    print("💡 Chrome остается открытым 30 секунд...", flush=True)
    time.sleep(30)

except Exception as e:
    print(f"❌ Ошибка: {e}", flush=True)
    import traceback
    traceback.print_exc()

finally:
    try:
        driver.quit()
    except:
        pass

    try:
        chrome_process.terminate()
    except:
        pass

    print("✅ Завершено", flush=True)
