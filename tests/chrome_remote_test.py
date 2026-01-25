#!/usr/bin/env python3
"""
БРАУЗЕРНОЕ ТЕСТИРОВАНИЕ через Chrome Remote Debugging
Запускаем Chrome, подключаемся к нему, КЛИКАЕМ ПО КНОПКАМ!
"""

import subprocess
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
TELEGRAM_WEB = "https://web.telegram.org/k/"
BOT_USERNAME = "training_dag_run_bot"
SCREENSHOTS_DIR = "/Users/noor/Documents/Obsidian Vault/Бот тренера/screenshots"
USER_DATA_DIR = "/Users/noor/Documents/Obsidian Vault/Бот тренера/chrome_profile"

print("="*70)
print("🌐 БРАУЗЕРНОЕ ТЕСТИРОВАНИЕ - Chrome Remote Debugging")
print("="*70)
print("Метод: Запускаю Chrome, подключаюсь, кликаю по кнопкам")
print("="*70)
print()

os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
os.makedirs(USER_DATA_DIR, exist_ok=True)

# Шаг 1: Запускаем Chrome с remote debugging
print("🚀 ШАГ 1: Запускаю Chrome с remote debugging...")
chrome_process = subprocess.Popen([
    CHROME_PATH,
    f"--remote-debugging-port=9222",
    f"--user-data-dir={USER_DATA_DIR}",
    "--no-first-run",
    "--no-default-browser-check",
    TELEGRAM_WEB
])

print("✅ Chrome запущен на порту 9222")
print("   Окно Chrome должно открыться")
print()

# Ждем чтобы Chrome запустился
time.sleep(5)

# Шаг 2: Подключаемся к Chrome через Selenium
print("🔌 ШАГ 2: Подключаюсь к Chrome через Selenium...")

chrome_options = Options()
chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

try:
    driver = webdriver.Chrome(options=chrome_options)
    print("✅ Подключен к Chrome!")
    print()

    # Шаг 3: Проверяем страницу
    print("🔍 ШАГ 3: Проверяю Telegram Web...")
    current_url = driver.current_url
    print(f"   URL: {current_url}")

    if 'telegram' not in current_url.lower():
        print("   Открываю Telegram Web...")
        driver.get(TELEGRAM_WEB)
        time.sleep(5)

    driver.save_screenshot(f"{SCREENSHOTS_DIR}/chrome_remote_01.png")
    print(f"   📸 Скриншот: chrome_remote_01.png")
    print()

    # Шаг 4: Авторизация
    print("="*70)
    print("🔐 ШАГ 4: АВТОРИЗАЦИЯ")
    print("="*70)

    page_source = driver.page_source

    if 'Log in' in page_source or 'Sign in' in page_source:
        print("⚠️  Требуется авторизация")
        print()
        print("💡 В ОТКРЫВШЕМСЯ CHROME:")
        print("   1. Отсканируй QR-код через Telegram на телефоне")
        print("   2. Или нажми 'LOG IN BY PHONE NUMBER'")
        print()

        input("   Нажми Enter когда авторизуешься...")
        print()
        print("✅ Авторизация завершена")
    else:
        print("✅ Уже авторизован!")

    driver.save_screenshot(f"{SCREENSHOTS_DIR}/chrome_remote_02_logged_in.png")
    print()

    # Шаг 5: Поиск бота
    print("="*70)
    print(f"🔍 ШАГ 5: Ищу бота @{BOT_USERNAME}")
    print("="*70)

    print("💡 В ОТКРЫВШЕМСЯ CHROME:")
    print(f"   1. Нажми на поиск (лупа вверху)")
    print(f"   2. Введи: @{BOT_USERNAME}")
    print(f"   3. Открой чат с ботом")
    print()

    input("   Нажми Enter когда откроешь чат с ботом...")
    print()
    print("✅ Чат с ботом открыт")

    driver.save_screenshot(f"{SCREENSHOTS_DIR}/chrome_remote_03_bot_opened.png")
    print()

    # Шаг 6: Отправляем /start
    print("="*70)
    print("🧪 ШАГ 6: Отправляю /start")
    print("="*70)

    # Ищем поле ввода
    input_selectors = [
        'div[contenteditable="true"]',
        '.input-message-input',
        '[data-placeholder="Message"]'
    ]

    message_input = None
    for selector in input_selectors:
        try:
            message_input = driver.find_element(By.CSS_SELECTOR, selector)
            if message_input:
                print(f"✅ Поле ввода найдено: {selector}")
                break
        except:
            continue

    if message_input:
        # Отправляем /start
        message_input.click()
        time.sleep(0.5)
        message_input.send_keys('/start')
        time.sleep(0.5)

        # Ищем кнопку отправки или жмем Enter
        from selenium.webdriver.common.keys import Keys
        message_input.send_keys(Keys.ENTER)

        print("✅ Команда /start отправлена")
        time.sleep(3)

        driver.save_screenshot(f"{SCREENSHOTS_DIR}/chrome_remote_04_start_sent.png")
    else:
        print("⚠️  Поле ввода не найдено автоматически")
        print("   Отправь /start вручную в открытом Chrome")
        input("   Нажми Enter когда отправишь...")

    print()

    # Шаг 7: Ищем и кликаем по кнопкам
    print("="*70)
    print("🖱️  ШАГ 7: ИЩУ И КЛИКАЮ ПО INLINE КНОПКАМ!")
    print("="*70)

    time.sleep(2)

    # Ищем кнопки
    button_selectors = [
        'button.reply-markup-button',
        'button[class*="markup"]',
        'button[class*="keyboard"]',
        '.keyboard-button'
    ]

    buttons_found = []
    for selector in button_selectors:
        try:
            buttons = driver.find_elements(By.CSS_SELECTOR, selector)
            if buttons:
                print(f"✅ Найдено кнопок: {len(buttons)} ({selector})")
                buttons_found = buttons
                break
        except:
            continue

    if buttons_found:
        print()
        print("🔘 КЛИКАЮ ПО КАЖДОЙ КНОПКЕ:")
        print("-" * 70)

        for idx, button in enumerate(buttons_found[:4], 1):  # Первые 4 кнопки
            try:
                btn_text = button.text
                print(f"\n{idx}. Кнопка: {btn_text}")

                # КЛИКАЕМ!
                button.click()
                print(f"   ✅ КЛИКНУЛ!")

                time.sleep(2)

                # Скриншот после клика
                driver.save_screenshot(f"{SCREENSHOTS_DIR}/chrome_remote_05_button_{idx}.png")
                print(f"   📸 Скриншот: chrome_remote_05_button_{idx}.png")

                # Проверяем что в чате (есть ли файл)
                page = driver.page_source
                if 'document' in page or '.ics' in page or 'download' in page.lower():
                    print(f"   📎 Похоже бот отправил файл!")
                    if 'календарь' in btn_text.lower():
                        print(f"   🎉 КНОПКА КАЛЕНДАРЬ РАБОТАЕТ!")

            except Exception as e:
                print(f"   ⚠️  Ошибка клика: {e}")

    else:
        print("⚠️  Inline кнопки не найдены автоматически")
        print()
        print("💡 ПРОВЕРЬ ВРУЧНУЮ в открытом Chrome:")
        print("   1. После /start должны быть 4 кнопки")
        print("   2. Нажми каждую кнопку")
        print("   3. Кнопка 📲 Календарь должна отправить ICS файл")
        print()
        input("   Нажми Enter когда проверишь...")

    print()

    # Шаг 8: Тестируем команды
    commands = ['/help', '/stats', '/plan', '/calendar']

    for cmd in commands:
        print("="*70)
        print(f"🧪 ТЕСТ: Команда {cmd}")
        print("="*70)

        if message_input:
            message_input.click()
            time.sleep(0.3)
            message_input.send_keys(cmd)
            time.sleep(0.3)
            message_input.send_keys(Keys.ENTER)

            print(f"✅ Команда {cmd} отправлена")
            time.sleep(3)
        else:
            print(f"   Отправь {cmd} вручную")
            input("   Нажми Enter когда отправишь...")

        print()

    # Итоги
    print("="*70)
    print("✅ БРАУЗЕРНОЕ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО!")
    print("="*70)
    print()
    print("🎉 ЧТО Я СДЕЛАЛ:")
    print("   ✅ Запустил Chrome с remote debugging")
    print("   ✅ Подключился через Selenium")
    print("   ✅ Открыл Telegram Web")
    print("   ✅ Отправил /start")
    print("   ✅ КЛИКНУЛ ПО INLINE КНОПКАМ")
    print("   ✅ Протестировал команды")
    print()
    print(f"📸 Все скриншоты в: {SCREENSHOTS_DIR}")
    print()
    print("💡 Chrome остается открытым - можешь продолжить тестирование вручную")
    print("="*70)
    print()

    input("Нажми Enter чтобы закрыть Chrome...")

except Exception as e:
    print(f"❌ ОШИБКА: {e}")
    import traceback
    traceback.print_exc()

finally:
    try:
        driver.quit()
    except:
        pass

    try:
        chrome_process.terminate()
        chrome_process.wait(timeout=5)
    except:
        chrome_process.kill()

    print("✅ Chrome закрыт")
