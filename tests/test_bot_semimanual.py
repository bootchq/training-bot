#!/usr/bin/env python3
"""
ПОЛУАВТОМАТИЧЕСКИЙ ТЕСТ БОТА С СОХРАНЕННОЙ СЕССИЕЙ

Запускай этот скрипт - Chrome откроется БЕЗ АВТОРИЗАЦИИ!
Открой бота @training_dag_run_bot вручную в Chrome
Скрипт автоматически отправит /start и кликнет по ВСЕМ кнопкам

✅ АВТОРИЗАЦИЯ НЕ НУЖНА - сессия сохранена!
"""

import time
import subprocess
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

BOT_USERNAME = 'training_dag_run_bot'
SCREENSHOTS_DIR = '/Users/noor/Documents/Obsidian Vault/Бот тренера/screenshots'
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE_DIR = os.path.expanduser("~/Library/Application Support/Google/Chrome/BotTesting")

print("="*70)
print("🤖 ПОЛУАВТОМАТИЧЕСКИЙ ТЕСТ БОТА")
print("="*70)
print()
print("✅ СЕССИЯ СОХРАНЕНА - авторизация НЕ НУЖНА!")
print()

os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

# Проверяем запущен ли Chrome
import requests
chrome_running = False
try:
    r = requests.get("http://127.0.0.1:9222/json/version", timeout=2)
    if r.status_code == 200:
        chrome_running = True
        print("✅ Chrome уже запущен")
except:
    pass

if not chrome_running:
    print("🚀 Запускаю Chrome с сохраненной сессией...")
    subprocess.Popen([
        CHROME_PATH,
        "--remote-debugging-port=9222",
        f"--user-data-dir={PROFILE_DIR}",
        "--profile-directory=Default",
        "--no-first-run",
        "https://web.telegram.org/k/"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print("⏳ Жду запуска Chrome...")
    time.sleep(10)

print()
print("="*70)
print("📋 ИНСТРУКЦИЯ:")
print("="*70)
print()
print(f"1. Открой бота @{BOT_USERNAME} в Chrome")
print("2. Нажми Enter здесь когда откроешь")
print()

input("Нажми Enter когда откроешь бота >>> ")

print()
print("✅ Начинаю автоматический тест...")
print()

# Подключаемся к Chrome
chrome_options = Options()
chrome_options.add_experimental_option('debuggerAddress', '127.0.0.1:9222')

driver = webdriver.Chrome(options=chrome_options)
print("✅ Подключен к Chrome")
print()

# Делаем скриншот
current_url = driver.current_url
print(f"📍 URL: {current_url}")
driver.save_screenshot(f"{SCREENSHOTS_DIR}/semi_01_bot.png")

time.sleep(2)

# Отправляем /start
print()
print("📝 Отправляю /start...")

start_sent = driver.execute_script("""
    // Ищем кнопку START
    var buttons = document.querySelectorAll('button');
    for (var i = 0; i < buttons.length; i++) {
        if (buttons[i].innerText && buttons[i].innerText.trim().toUpperCase() === 'START') {
            buttons[i].click();
            return 'button';
        }
    }

    // Или через поле ввода
    var input = document.querySelector('div[contenteditable="true"]');
    if (input) {
        input.focus();
        input.textContent = '/start';

        var event = new KeyboardEvent('keydown', {
            bubbles: true,
            cancelable: true,
            key: 'Enter',
            code: 'Enter',
            keyCode: 13
        });
        input.dispatchEvent(event);

        return 'input';
    }

    return false;
""")

if start_sent:
    print(f"✅ /start отправлен (через {start_sent})")
else:
    print("⚠️  Не удалось отправить /start автоматически")
    print("   Отправь /start вручную и нажми Enter")
    input("Нажми Enter >>> ")

time.sleep(4)
driver.save_screenshot(f"{SCREENSHOTS_DIR}/semi_02_start.png")

print()
print("🔘 Ищу inline кнопки...")
time.sleep(2)

# Получаем все inline кнопки
buttons_data = driver.execute_script("""
    var buttons = document.querySelectorAll('button.reply-markup-button');
    var result = [];

    for (var i = 0; i < buttons.length; i++) {
        var btn = buttons[i];
        if (btn.innerText && btn.innerText.trim()) {
            result.push(btn.innerText.trim());
        }
    }

    return result;
""")

if buttons_data and len(buttons_data) > 0:
    print(f"✅ Найдено {len(buttons_data)} кнопок:")
    for i, text in enumerate(buttons_data, 1):
        print(f"   {i}. {text}")

    print()
    print("🖱️  АВТОМАТИЧЕСКИ КЛИКАЮ ПО ВСЕМ КНОПКАМ:")
    print("-" * 70)

    for idx in range(len(buttons_data)):
        print(f"\n{idx+1}. '{buttons_data[idx]}'")

        # Кликаем через JavaScript
        driver.execute_script(f"""
            var buttons = document.querySelectorAll('button.reply-markup-button');
            if (buttons[{idx}]) {{
                buttons[{idx}].scrollIntoView({{behavior: 'smooth', block: 'center'}});
                setTimeout(function() {{
                    buttons[{idx}].click();
                }}, 300);
            }}
        """)

        print(f"   ✅ КЛИКНУЛ")
        time.sleep(3)

        driver.save_screenshot(f"{SCREENSHOTS_DIR}/semi_03_btn{idx+1}.png")

        # Проверяем результат
        page_source = driver.page_source
        if '.ics' in page_source:
            print(f"   🎉 ICS ФАЙЛ ОТПРАВЛЕН!")
        elif 'oauth' in page_source.lower():
            print(f"   ⚠️  OAuth ошибка обнаружена")

    print()
    print("="*70)
    print("✅ ВСЕ КНОПКИ ПРОТЕСТИРОВАНЫ!")
    print("="*70)
    print()
    print(f"📸 Скриншоты: {SCREENSHOTS_DIR}")
    print()
    print("💡 Chrome остается открытым")
    print("   Сессия сохранена - в следующий раз авторизация НЕ НУЖНА!")

else:
    print("⚠️  Inline кнопки не найдены")
    print()
    print("Возможные причины:")
    print("- Бот не открыт")
    print("- /start не был отправлен")
    print("- Бот не отвечает")

    # Показываем текст страницы
    page_text = driver.execute_script("return document.body.innerText;")
    print()
    print("Текст на странице (первые 500 символов):")
    print(page_text[:500])

print()
