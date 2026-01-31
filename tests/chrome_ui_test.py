#!/usr/bin/env python3
"""
Браузерное тестирование через установленный Google Chrome
Использует системный Chrome, а не загруженный Chromium
"""

import os
import time
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

BOT_USERNAME = "training_dag_run_bot"
SCREENSHOTS_DIR = "/Users/noor/Documents/Obsidian Vault/Бот тренера/screenshots"

def main():
    print("\n" + "="*70)
    print("🌐 БРАУЗЕРНОЕ ТЕСТИРОВАНИЕ ЧЕРЕЗ GOOGLE CHROME")
    print("="*70)
    print(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Браузер: Google Chrome (системный)")
    print(f"Бот: @{BOT_USERNAME}")
    print("="*70 + "\n")

    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

    print("🚀 Запускаю Google Chrome...")

    # Настройки Chrome
    chrome_options = Options()

    # Указываем путь к системному Chrome
    chrome_options.binary_location = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

    # НЕ ИСПОЛЬЗУЕМ headless - открываем полноценный браузер
    # chrome_options.add_argument('--headless')  # ОТКЛЮЧЕНО

    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1280,800')

    try:
        # ChromeDriver
        print("📥 Установка ChromeDriver...")
        service = Service(ChromeDriverManager().install())

        # Запускаем браузер
        print("✅ ChromeDriver готов")
        print("🚀 Открываю Chrome...")

        driver = webdriver.Chrome(service=service, options=chrome_options)

        print("✅ Chrome запущен (окно должно открыться)")

        # Открываем Telegram Web
        print("\n📱 Открываю Telegram Web...")
        driver.get('https://web.telegram.org/k/')
        time.sleep(5)

        driver.save_screenshot(f'{SCREENSHOTS_DIR}/chrome_01_telegram.png')
        print("✅ Telegram Web открыт")
        print(f"   URL: {driver.current_url}")
        print(f"   Скриншот: {SCREENSHOTS_DIR}/chrome_01_telegram.png")

        # Проверяем авторизацию
        print("\n🔍 Проверка авторизации...")
        page_source = driver.page_source

        if 'Sign in to Telegram' in page_source or 'Log in to Telegram' in page_source:
            print("📱 Требуется авторизация")
            print("\n💡 ИНСТРУКЦИЯ:")
            print("   1. Отсканируй QR-код через приложение Telegram на телефоне:")
            print("      • Открой Telegram на телефоне")
            print("      • Настройки → Устройства → Привязать устройство")
            print("      • Наведи камеру на QR-код в открывшемся Chrome")
            print()
            print("   2. Или нажми 'LOG IN BY PHONE NUMBER' в браузере")
            print()

            driver.save_screenshot(f'{SCREENSHOTS_DIR}/chrome_02_qr_code.png')
            print(f"   Скриншот QR-кода: {SCREENSHOTS_DIR}/chrome_02_qr_code.png")

            # Ждем авторизации
            print("\n⏳ Жду авторизацию (5 минут)...")
            print("   Скрипт автоматически продолжит после авторизации")

            max_wait = 300  # 5 минут
            start = time.time()

            while time.time() - start < max_wait:
                time.sleep(3)

                # Проверяем
                current_page = driver.page_source
                if 'Sign in to Telegram' not in current_page and 'Log in to Telegram' not in current_page:
                    print("\n✅ Авторизация успешна!")
                    break

                remaining = int(max_wait - (time.time() - start))
                mins, secs = divmod(remaining, 60)
                print(f"   Осталось: {mins:02d}:{secs:02d}   ", end='\r')

            else:
                print("\n❌ Время истекло")
                print("   Перезапусти скрипт и авторизуйся быстрее")
                print("   Или оставь браузер открытым и запусти скрипт заново")
                return

        else:
            print("✅ Уже авторизован!")

        # Скриншот после авторизации
        time.sleep(2)
        driver.save_screenshot(f'{SCREENSHOTS_DIR}/chrome_03_authorized.png')
        print(f"\n   Скриншот: {SCREENSHOTS_DIR}/chrome_03_authorized.png")

        # Поиск бота
        print("\n" + "="*70)
        print("🔍 ПОИСК БОТА")
        print("="*70)

        print("\n💡 В открывшемся Chrome найди бота:")
        print("   1. Нажми на иконку поиска (лупа)")
        print(f"   2. Введи: @{BOT_USERNAME}")
        print("   3. Открой чат с ботом")

        input("\n   Нажми Enter в терминале когда откроешь чат с ботом...")

        driver.save_screenshot(f'{SCREENSHOTS_DIR}/chrome_04_bot_opened.png')
        print("✅ Чат с ботом открыт")
        print(f"   Скриншот: {SCREENSHOTS_DIR}/chrome_04_bot_opened.png")

        # Тестирование
        print("\n" + "="*70)
        print("🧪 ТЕСТИРОВАНИЕ КОМАНД И КНОПОК")
        print("="*70)

        print("\n💡 ПЛАН ТЕСТИРОВАНИЯ:")
        print("   1. Отправь /start")
        print("   2. Проверь что появились 4 inline кнопки:")
        print("      • 📊 Статистика")
        print("      • 📅 План")
        print("      • 🔄 Синхронизация")
        print("      • 📲 Календарь")
        print()
        print("   3. Нажми каждую кнопку и проверь что работает")
        print()
        print("   4. Протестируй команды:")
        print("      • /help - справка")
        print("      • /stats - статистика (если зарегистрирован Garmin)")
        print("      • /plan - генерация плана")
        print("      • /calendar - скачивание ICS файла")
        print()
        print("   5. Проверь что:")
        print("      • Сообщения форматируются правильно (Markdown)")
        print("      • Календарь отправляет файл .ics")
        print("      • Нет ошибок в консоли")

        input("\n   Протестируй в браузере, затем нажми Enter...")

        # Финальный скриншот
        driver.save_screenshot(f'{SCREENSHOTS_DIR}/chrome_05_final.png')
        print(f"\n✅ Финальный скриншот: {SCREENSHOTS_DIR}/chrome_05_final.png")

        # Итоги
        print("\n" + "="*70)
        print("📊 ИТОГИ ТЕСТИРОВАНИЯ")
        print("="*70)
        print("✅ Браузерное тестирование через Google Chrome завершено")
        print(f"✅ Скриншоты сохранены: {SCREENSHOTS_DIR}")
        print("\n💡 Теперь ты можешь:")
        print("   • Проверить скриншоты")
        print("   • Запустить скрипт снова (авторизация сохранится)")
        print("   • Протестировать другие сценарии")
        print("="*70 + "\n")

        print("Закрываю браузер через 10 секунд...")
        time.sleep(10)

    except Exception as e:
        print(f"\n❌ ОШИБКА: {type(e).__name__}: {e}")

        print("\n💡 ВОЗМОЖНЫЕ РЕШЕНИЯ:")
        print("   1. Закрой все окна Chrome и попробуй снова")
        print("   2. Обнови ChromeDriver: pip3 install --upgrade webdriver-manager")
        print("   3. Проверь что Google Chrome установлен в /Applications/")

        import traceback
        traceback.print_exc()

    finally:
        try:
            driver.quit()
            print("✅ Браузер закрыт")
        except:
            pass

if __name__ == "__main__":
    main()
