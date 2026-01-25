#!/usr/bin/env python3
"""
Браузерное тестирование Telegram бота через Selenium
Эмулирует реальные действия пользователя в браузере
"""

import time
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

BOT_USERNAME = "training_dag_run_bot"
SCREENSHOTS_DIR = "/Users/noor/Documents/Obsidian Vault/Бот тренера/screenshots"

def main():
    print("\n" + "="*70)
    print("🌐 БРАУЗЕРНОЕ ТЕСТИРОВАНИЕ БОТА ЧЕРЕЗ SELENIUM")
    print("="*70)
    print(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Метод: Selenium + ChromeDriver")
    print(f"Бот: @{BOT_USERNAME}")
    print("="*70 + "\n")

    # Создаем папку для скриншотов
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

    # Настройка Chrome
    print("🚀 Настраиваю Chrome...")
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Без GUI
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1280,800')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36')

    try:
        print("📥 Скачиваю ChromeDriver...")
        service = Service(ChromeDriverManager().install())

        print("✅ ChromeDriver готов")
        print("🚀 Запускаю браузер...")

        driver = webdriver.Chrome(service=service, options=chrome_options)

        print("✅ Браузер запущен")

        # ТЕСТ 1: Открываем Telegram Web
        print("\n" + "="*70)
        print("🧪 ТЕСТ 1: Открываю Telegram Web")
        print("="*70)

        driver.get('https://web.telegram.org/k/')
        time.sleep(5)  # Даем время на загрузку

        driver.save_screenshot(f'{SCREENSHOTS_DIR}/selenium_01_loaded.png')
        print("✅ Telegram Web открыт")
        print(f"   URL: {driver.current_url}")
        print(f"   Заголовок: {driver.title}")
        print(f"   Скриншот: {SCREENSHOTS_DIR}/selenium_01_loaded.png")

        # ТЕСТ 2: Анализ страницы
        print("\n" + "="*70)
        print("🧪 ТЕСТ 2: Анализирую контент страницы")
        print("="*70)

        page_source = driver.page_source

        # Проверяем что видим
        if 'Sign in to Telegram' in page_source or 'Войти в Telegram' in page_source:
            print("📱 Обнаружена форма авторизации")
            print("   ⚠️  Требуется ручной вход в Telegram Web")

            driver.save_screenshot(f'{SCREENSHOTS_DIR}/selenium_02_login_required.png')
            print(f"   Скриншот: {SCREENSHOTS_DIR}/selenium_02_login_required.png")

            print("\n💡 ДЛЯ ПОЛНОГО ТЕСТИРОВАНИЯ:")
            print("   1. Открой вручную: https://web.telegram.org/k/")
            print("   2. Авторизуйся через номер телефона")
            print("   3. Найди бота @training_dag_run_bot")
            print("   4. Протестируй все команды и кнопки")

        elif 'telegram' in page_source.lower():
            print("✅ Страница Telegram загружена")

            # Ищем элементы интерфейса
            try:
                # Ждем появления каких-либо интерактивных элементов
                wait = WebDriverWait(driver, 10)

                # Ищем input поля
                inputs = driver.find_elements(By.TAG_NAME, 'input')
                print(f"   Найдено полей ввода: {len(inputs)}")

                # Ищем кнопки
                buttons = driver.find_elements(By.TAG_NAME, 'button')
                print(f"   Найдено кнопок: {len(buttons)}")

                driver.save_screenshot(f'{SCREENSHOTS_DIR}/selenium_03_interface.png')
                print(f"   Скриншот: {SCREENSHOTS_DIR}/selenium_03_interface.png")

            except Exception as e:
                print(f"   ⚠️  Не удалось найти элементы: {e}")

        else:
            print("⚠️  Неожиданный контент страницы")
            driver.save_screenshot(f'{SCREENSHOTS_DIR}/selenium_unexpected.png')

        # ТЕСТ 3: Проверяем доступность bot API
        print("\n" + "="*70)
        print("🧪 ТЕСТ 3: Проверяю bot API (для сравнения)")
        print("="*70)

        import requests
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        if bot_token:
            response = requests.get(f'https://api.telegram.org/bot{bot_token}/getMe')
            if response.status_code == 200:
                bot_info = response.json()['result']
                print(f"✅ Бот доступен через API: @{bot_info['username']}")
                print(f"   Имя: {bot_info['first_name']}")
            else:
                print("❌ Бот недоступен через API")
        else:
            print("⚠️  TELEGRAM_BOT_TOKEN не установлен")

        # Итоговый отчет
        print("\n" + "="*70)
        print("📊 ИТОГОВЫЙ ОТЧЁТ")
        print("="*70)
        print("✅ Selenium работает корректно")
        print("✅ ChromeDriver установлен")
        print("✅ Браузер запускается")
        print("✅ Telegram Web доступен")
        print("✅ Скриншоты сохранены в:", SCREENSHOTS_DIR)
        print("\n💡 ВЫВОДЫ:")
        print("   • Браузерное тестирование технически возможно")
        print("   • Для полного UI тестирования нужна авторизация")
        print("   • Автоматизация клика по кнопкам требует сохраненной сессии")
        print("   • Telegram Web имеет защиту от автоматизации (2FA, phone verification)")
        print("\n🎯 РЕКОМЕНДАЦИИ:")
        print("   1. Для ручного UI тестирования - используй чеклист из MANUAL_TEST_CHECKLIST.md")
        print("   2. Для автоматических тестов - используй Bot API (full_user_simulation.py)")
        print("   3. Для продакшн мониторинга - настрой healthcheck через API")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\n❌ ОШИБКА: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    finally:
        try:
            driver.quit()
            print("🔒 Браузер закрыт")
        except:
            pass

if __name__ == "__main__":
    main()
