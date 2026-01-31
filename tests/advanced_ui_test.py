#!/usr/bin/env python3
"""
Продвинутое браузерное тестирование бота с авторизацией
Позволяет авторизоваться в Telegram Web и протестировать все кнопки бота
"""

import os
import time
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

BOT_USERNAME = "training_dag_run_bot"
SCREENSHOTS_DIR = "/Users/noor/Documents/Obsidian Vault/Бот тренера/screenshots"
USER_DATA_DIR = "/Users/noor/Documents/Obsidian Vault/Бот тренера/chrome_session"

def setup_browser(headless=False):
    """Настройка браузера с сохранением сессии"""
    chrome_options = Options()

    if headless:
        chrome_options.add_argument('--headless')

    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1280,800')
    chrome_options.add_argument(f'--user-data-dir={USER_DATA_DIR}')
    chrome_options.add_argument('--profile-directory=Default')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    return driver

def test_login_required(driver):
    """Проверяем нужна ли авторизация"""
    page_source = driver.page_source
    return 'Sign in to Telegram' in page_source or 'Log in to Telegram' in page_source

def wait_for_login(driver, timeout=300):
    """Ждем пока пользователь авторизуется"""
    print("\n" + "="*70)
    print("⏳ АВТОРИЗАЦИЯ")
    print("="*70)
    print("📱 Открыто окно браузера для авторизации")
    print("   Пожалуйста, авторизуйся в Telegram:")
    print("   1. Отсканируй QR-код через мобильное приложение Telegram")
    print("   2. Или нажми 'LOG IN BY PHONE NUMBER' и введи номер")
    print(f"\n⏱  Ожидание авторизации ({timeout} сек)...")

    start_time = time.time()
    while time.time() - start_time < timeout:
        if not test_login_required(driver):
            print("✅ Авторизация успешна!")
            return True

        time.sleep(2)

    print("❌ Время ожидания истекло")
    return False

def find_bot(driver, bot_username):
    """Поиск бота в Telegram"""
    print("\n" + "="*70)
    print(f"🔍 ПОИСК БОТА @{bot_username}")
    print("="*70)

    try:
        # Ждем загрузки интерфейса
        time.sleep(3)

        # Ищем поле поиска (разные варианты селекторов)
        search_selectors = [
            'input[placeholder*="Search"]',
            'input.input-search',
            '//input[@type="text"]',
        ]

        search_input = None
        for selector in search_selectors:
            try:
                if selector.startswith('//'):
                    search_input = driver.find_element(By.XPATH, selector)
                else:
                    search_input = driver.find_element(By.CSS_SELECTOR, selector)

                if search_input:
                    print("✅ Найдено поле поиска")
                    break
            except Exception:
                continue

        if not search_input:
            print("⚠️  Автоматический поиск не удался")
            print("   Найди бота вручную: @" + bot_username)
            input("   Нажми Enter когда откроешь чат с ботом...")
            return True

        # Кликаем в поиск и вводим имя бота
        search_input.click()
        time.sleep(1)

        search_input.send_keys(f'@{bot_username}')
        time.sleep(2)

        driver.save_screenshot(f'{SCREENSHOTS_DIR}/04_search_bot.png')
        print(f"   Скриншот: {SCREENSHOTS_DIR}/04_search_bot.png")

        # Нажимаем Enter
        search_input.send_keys(Keys.ENTER)
        time.sleep(3)

        print(f"✅ Бот @{bot_username} найден")
        return True

    except Exception as e:
        print(f"⚠️  Ошибка поиска: {e}")
        print("   Найди бота вручную: @" + bot_username)
        input("   Нажми Enter когда откроешь чат с ботом...")
        return True

def test_bot_commands(driver):
    """Тестирование команд и кнопок бота"""
    print("\n" + "="*70)
    print("🧪 ТЕСТИРОВАНИЕ КОМАНД БОТА")
    print("="*70)

    try:
        # Ищем поле ввода сообщения
        message_selectors = [
            '.input-message-input',
            '[contenteditable="true"]',
            'div.input-message-container textarea',
        ]

        message_input = None
        for selector in message_selectors:
            try:
                message_input = driver.find_element(By.CSS_SELECTOR, selector)
                if message_input:
                    print("✅ Найдено поле ввода сообщения")
                    break
            except Exception:
                continue

        if not message_input:
            print("⚠️  Не удалось найти поле ввода")
            print("   Протестируй команды вручную:")
            print("   1. Отправь /start")
            print("   2. Проверь inline кнопки")
            print("   3. Протестируй каждую команду")
            input("\n   Нажми Enter когда закончишь тестирование...")
            return

        # ТЕСТ 1: Команда /start
        print("\n📝 Тест 1: Отправляю /start")
        message_input.click()
        time.sleep(0.5)

        message_input.send_keys('/start')
        time.sleep(0.5)

        message_input.send_keys(Keys.ENTER)
        time.sleep(3)

        driver.save_screenshot(f'{SCREENSHOTS_DIR}/05_start_command.png')
        print("✅ Команда /start отправлена")
        print(f"   Скриншот: {SCREENSHOTS_DIR}/05_start_command.png")

        # Проверяем наличие inline кнопок
        time.sleep(2)
        buttons = driver.find_elements(By.CSS_SELECTOR, 'button.reply-markup-button')
        print(f"   Найдено inline кнопок: {len(buttons)}")

        if len(buttons) > 0:
            print("   Кнопки:")
            for i, btn in enumerate(buttons[:10], 1):  # Показываем первые 10
                try:
                    btn_text = btn.text
                    if btn_text:
                        print(f"     {i}. {btn_text}")
                except Exception:
                    pass

        # ТЕСТ 2: Команда /help
        print("\n📝 Тест 2: Отправляю /help")
        message_input.click()
        message_input.send_keys('/help')
        message_input.send_keys(Keys.ENTER)
        time.sleep(3)

        driver.save_screenshot(f'{SCREENSHOTS_DIR}/06_help_command.png')
        print("✅ Команда /help отправлена")
        print(f"   Скриншот: {SCREENSHOTS_DIR}/06_help_command.png")

        # ТЕСТ 3: Проверяем кнопки
        if len(buttons) > 0:
            print("\n📝 Тест 3: Проверяю inline кнопки")
            print("   (клик по первой кнопке)")

            try:
                first_button = buttons[0]
                btn_text = first_button.text
                print(f"   Нажимаю кнопку: {btn_text}")

                first_button.click()
                time.sleep(3)

                driver.save_screenshot(f'{SCREENSHOTS_DIR}/07_button_click.png')
                print("✅ Кнопка нажата")
                print(f"   Скриншот: {SCREENSHOTS_DIR}/07_button_click.png")

            except Exception as e:
                print(f"⚠️  Не удалось нажать кнопку: {e}")

        print("\n💡 РУЧНОЕ ТЕСТИРОВАНИЕ:")
        print("   Теперь протестируй вручную:")
        print("   • Все inline кнопки")
        print("   • Команды /stats, /plan, /calendar")
        print("   • Проверь что календарь отправляет ICS файл")
        print("   • Проверь что все сообщения отображаются корректно")
        input("\n   Нажми Enter когда закончишь...")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

def main():
    print("\n" + "="*70)
    print("🌐 ПРОДВИНУТОЕ БРАУЗЕРНОЕ ТЕСТИРОВАНИЕ БОТА")
    print("="*70)
    print(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Метод: Selenium + ChromeDriver + Session")
    print(f"Бот: @{BOT_USERNAME}")
    print("="*70)

    # Создаем папки
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    os.makedirs(USER_DATA_DIR, exist_ok=True)

    # Режим запуска
    print("\n💡 Режимы запуска:")
    print("   1. С графическим интерфейсом (для авторизации)")
    print("   2. Headless (если уже авторизован)")

    # По умолчанию - с GUI для первого запуска
    headless = False

    # Запускаем браузер
    print("\n🚀 Запускаю браузер...")
    driver = setup_browser(headless=headless)

    try:
        # Открываем Telegram Web
        print("🌐 Открываю Telegram Web...")
        driver.get('https://web.telegram.org/k/')
        time.sleep(5)

        driver.save_screenshot(f'{SCREENSHOTS_DIR}/01_initial.png')

        # Проверяем авторизацию
        if test_login_required(driver):
            print("🔐 Требуется авторизация")

            # Ждем авторизации
            if not wait_for_login(driver, timeout=300):
                print("\n❌ Не удалось авторизоваться")
                print("   Перезапусти скрипт и авторизуйся")
                return

            # Сохраняем скриншот после авторизации
            driver.save_screenshot(f'{SCREENSHOTS_DIR}/02_logged_in.png')
            print(f"✅ Сессия сохранена в: {USER_DATA_DIR}")

        else:
            print("✅ Уже авторизован (используется сохраненная сессия)")

        # Ищем бота
        find_bot(driver, BOT_USERNAME)

        # Сохраняем скриншот чата с ботом
        driver.save_screenshot(f'{SCREENSHOTS_DIR}/03_bot_chat.png')
        print(f"   Скриншот: {SCREENSHOTS_DIR}/03_bot_chat.png")

        # Тестируем команды
        test_bot_commands(driver)

        # Итоговый отчет
        print("\n" + "="*70)
        print("📊 ИТОГОВЫЙ ОТЧЁТ")
        print("="*70)
        print("✅ Браузерное тестирование завершено")
        print("✅ Все скриншоты сохранены в:", SCREENSHOTS_DIR)
        print("✅ Сессия сохранена в:", USER_DATA_DIR)
        print("\n💡 Следующий запуск будет использовать сохраненную сессию")
        print("   (авторизация не потребуется)")
        print("="*70 + "\n")

        print("🔒 Закрываю браузер через 10 секунд...")
        time.sleep(10)

    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем")

    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()

    finally:
        driver.quit()
        print("✅ Браузер закрыт")

if __name__ == "__main__":
    main()
