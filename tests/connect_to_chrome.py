#!/usr/bin/env python3
"""
ПОДКЛЮЧЕНИЕ К УЖЕ ЗАПУЩЕННОМУ CHROME
Если у тебя открыт Chrome с Telegram - просто подключусь к нему!
Сессия сохранена, авторизация НЕ НУЖНА!
"""

import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

TELEGRAM_WEB = "https://web.telegram.org/k/"
BOT_USERNAME = "training_dag_run_bot"
SCREENSHOTS_DIR = "/Users/noor/Documents/Obsidian Vault/Бот тренера/screenshots"

print("="*70, flush=True)
print("🌐 ПОДКЛЮЧЕНИЕ К ТВОЕМУ CHROME", flush=True)
print("="*70, flush=True)
print(flush=True)

os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

print("💡 ИНСТРУКЦИЯ:", flush=True)
print("   1. Открой Google Chrome ВРУЧНУЮ", flush=True)
print("   2. Запусти Chrome с флагом:", flush=True)
print("      /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222", flush=True)
print("   3. Авторизуйся в Telegram Web (один раз)", flush=True)
print("   4. Запусти этот скрипт снова", flush=True)
print(flush=True)

# Пробуем подключиться
print("🔌 Пытаюсь подключиться к Chrome на порту 9222...", flush=True)

chrome_options = Options()
chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

try:
    driver = webdriver.Chrome(options=chrome_options)
    print("✅ Подключен к твоему Chrome!", flush=True)
    print(flush=True)

    # Получаем текущий URL
    current_url = driver.current_url
    print(f"📍 Текущая страница: {current_url}", flush=True)

    # Открываем бота
    print(f"🔍 Открываю бота @{BOT_USERNAME}...", flush=True)
    bot_url = f"https://web.telegram.org/k/#{BOT_USERNAME}"
    driver.get(bot_url)
    time.sleep(5)

    print("✅ Чат с ботом открыт", flush=True)
    driver.save_screenshot(f"{SCREENSHOTS_DIR}/connected_01.png")
    print(flush=True)

    # Отправляем /start
    print("📝 Отправляю /start...", flush=True)

    input_selectors = [
        'div[contenteditable="true"]',
        '.input-message-input',
        'div.input-message-input'
    ]

    message_input = None
    for selector in input_selectors:
        try:
            message_input = driver.find_element(By.CSS_SELECTOR, selector)
            if message_input:
                print(f"   Найдено поле ввода: {selector}", flush=True)
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
        driver.save_screenshot(f"{SCREENSHOTS_DIR}/connected_02_start.png")
    else:
        print("⚠️  Поле ввода не найдено", flush=True)

    print(flush=True)

    # Ищем кнопки
    print("🔘 Ищу inline кнопки...", flush=True)
    time.sleep(2)

    button_selectors = [
        'button.reply-markup-button',
        'button[class*="Button"]'
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

                # КЛИКАЕМ!
                btn.click()
                print(f"   ✅ КЛИКНУЛ!", flush=True)
                time.sleep(2)

                # Скриншот
                driver.save_screenshot(f"{SCREENSHOTS_DIR}/connected_03_btn_{idx}.png")
                print(f"   📸 Скриншот сохранен", flush=True)

                # Проверяем ответ
                page = driver.page_source
                if '.ics' in page or 'document' in page:
                    if 'календарь' in btn_text.lower():
                        print(f"   🎉 КНОПКА КАЛЕНДАРЬ ОТПРАВИЛА ФАЙЛ!", flush=True)

            except Exception as e:
                print(f"   ⚠️  Ошибка: {e}", flush=True)

        print(flush=True)
        print("="*70, flush=True)
        print("✅ ВСЕ КНОПКИ ПРОТЕСТИРОВАНЫ!", flush=True)
        print("="*70, flush=True)

    else:
        print("⚠️  Кнопки не найдены", flush=True)

    print(flush=True)
    print(f"📸 Скриншоты в: {SCREENSHOTS_DIR}", flush=True)
    print(flush=True)
    print("💡 Chrome остается открытым - можешь продолжить вручную", flush=True)
    print("   Закрой этот скрипт когда закончишь", flush=True)
    print(flush=True)

    # НЕ закрываем Chrome!
    print("⏳ Жду 60 секунд...", flush=True)
    time.sleep(60)

except Exception as e:
    print(f"❌ Ошибка: {e}", flush=True)
    print(flush=True)
    print("💡 РЕШЕНИЕ:", flush=True)
    print("   Chrome не запущен с remote debugging", flush=True)
    print(flush=True)
    print("   Запусти Chrome вручную:", flush=True)
    print('   /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222 &', flush=True)
    print(flush=True)
    print("   Затем перезапусти этот скрипт", flush=True)

finally:
    print("✅ Завершено", flush=True)
