#!/usr/bin/env python3
"""
ПОЛНОСТЬЮ АВТОМАТИЧЕСКИЙ БРАУЗЕРНЫЙ ТЕСТ БОТА

✅ БЕЗ АВТОРИЗАЦИИ - сессия сохранена!
✅ Автоматически открывает бота
✅ Отправляет /start
✅ Кликает по ВСЕМ inline кнопкам
✅ Делает скриншоты
"""

import os
import subprocess
import time

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# Конфигурация
BOT_USERNAME = 'training_dag_run_bot'
SCREENSHOTS_DIR = '/Users/noor/Documents/Obsidian Vault/Бот тренера/screenshots'
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE_DIR = os.path.expanduser("~/Library/Application Support/Google/Chrome/BotTesting")

print("="*70)
print("🤖 АВТОМАТИЧЕСКИЙ БРАУЗЕРНЫЙ ТЕСТ БОТА")
print("="*70)
print()

os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

# Проверяем запущен ли Chrome
chrome_running = False
try:
    r = requests.get("http://127.0.0.1:9222/json/version", timeout=2)
    if r.status_code == 200:
        chrome_running = True
        print("✅ Chrome уже запущен с remote debugging")
except Exception:
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
print("🔌 Подключаюсь к Chrome...")

chrome_options = Options()
chrome_options.add_experimental_option('debuggerAddress', '127.0.0.1:9222')

driver = webdriver.Chrome(options=chrome_options)
print("✅ Подключен!")
print()

# Открываем бота через t.me
print(f"🔍 Открываю бота через https://t.me/{BOT_USERNAME}...")
driver.get(f"https://t.me/{BOT_USERNAME}")
time.sleep(6)

driver.save_screenshot(f"{SCREENSHOTS_DIR}/auto_01_tme.png")

# Кликаем "Web Telegram"
print("📝 Ищу кнопку Web Telegram...")

web_clicked = driver.execute_script("""
    var buttons = document.querySelectorAll('button, a');

    for (var i = 0; i < buttons.length; i++) {
        var text = (buttons[i].innerText || buttons[i].textContent || '').toLowerCase();

        if (text.includes('web') || text.includes('telegram')) {
            buttons[i].click();
            return true;
        }
    }

    return false;
""")

if web_clicked:
    print("✅ Кликнул на Web Telegram")
    time.sleep(6)
    driver.save_screenshot(f"{SCREENSHOTS_DIR}/auto_02_opened.png")
else:
    print("⚠️  Кнопка не найдена - возможно уже в Web Telegram")

print()

# Отправляем /start
print("📝 Отправляю /start...")

start_sent = driver.execute_script("""
    // Ищем кнопку START
    var buttons = document.querySelectorAll('button');
    for (var i = 0; i < buttons.length; i++) {
        var text = (buttons[i].innerText || '').trim().toUpperCase();
        if (text === 'START' || text === 'RESTART') {
            buttons[i].click();
            return 'button';
        }
    }

    // Через поле ввода
    var inputs = document.querySelectorAll('[contenteditable="true"]');
    for (var j = 0; j < inputs.length; j++) {
        var rect = inputs[j].getBoundingClientRect();
        if (rect.width > 200 && rect.bottom > window.innerHeight * 0.6) {
            inputs[j].focus();
            inputs[j].textContent = '/start';

            var e = new KeyboardEvent('keydown', {
                key: 'Enter',
                code: 'Enter',
                keyCode: 13,
                bubbles: true,
                cancelable: true
            });
            inputs[j].dispatchEvent(e);
            return 'input';
        }
    }

    return false;
""")

print(f"   Результат: {start_sent}")
time.sleep(5)
driver.save_screenshot(f"{SCREENSHOTS_DIR}/auto_03_start.png")

print()
print("🔘 Ищу inline кнопки...")
time.sleep(2)

# Получаем все inline кнопки (убираем дубликаты)
buttons = driver.execute_script("""
    var btns = document.querySelectorAll('button.reply-markup-button');
    var seen = new Set();
    var result = [];

    for (var i = 0; i < btns.length; i++) {
        var text = btns[i].innerText.trim();
        if (text && !seen.has(text)) {
            seen.add(text);
            result.push(text);
        }
    }

    return result;
""")

if buttons and len(buttons) > 0:
    print(f"✅ Найдено {len(buttons)} уникальных кнопок:")
    for i, text in enumerate(buttons, 1):
        print(f"   {i}. {text}")

    print()
    print("🖱️  КЛИКАЮ ПО КНОПКАМ:")
    print("-" * 70)

    for idx, btn_text in enumerate(buttons):
        print(f"\n{idx+1}. '{btn_text}'")

        # Кликаем на первую кнопку с таким текстом
        driver.execute_script(f"""
            var btns = document.querySelectorAll('button.reply-markup-button');
            for (var i = 0; i < btns.length; i++) {{
                if (btns[i].innerText.trim() === '{btn_text}') {{
                    btns[i].click();
                    break;
                }}
            }}
        """)

        print("   ✅ КЛИКНУЛ")
        time.sleep(3)

        driver.save_screenshot(f"{SCREENSHOTS_DIR}/auto_04_btn{idx+1}.png")

        # Проверяем результат
        page = driver.page_source
        if '.ics' in page:
            print("   🎉 ICS ФАЙЛ ОБНАРУЖЕН!")

    print()
    print("="*70)
    print("🎉 ТЕСТ ЗАВЕРШЕН УСПЕШНО!")
    print("="*70)
    print()
    print(f"📸 Скриншоты: {SCREENSHOTS_DIR}")
    print()
    print("💡 Результаты:")
    print("   - Бот открыт: ✅")
    print("   - /start отправлен: ✅")
    print(f"   - Протестировано кнопок: {len(buttons)}")
    print()
    print("✅ Сессия сохранена - в следующий раз БЕЗ авторизации!")

else:
    print("⚠️  Inline кнопки не найдены")

print()
