#!/usr/bin/env python3
"""
Браузерное тестирование через Safari
Safari встроен в macOS и не требует установки
"""

import time
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.safari.options import Options as SafariOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

BOT_USERNAME = "training_dag_run_bot"
SCREENSHOTS_DIR = "/Users/noor/Documents/Obsidian Vault/Бот тренера/screenshots"

def main():
    print("\n" + "="*70)
    print("🌐 БРАУЗЕРНОЕ ТЕСТИРОВАНИЕ ЧЕРЕЗ SAFARI")
    print("="*70)
    print(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Браузер: Safari (встроенный)")
    print(f"Бот: @{BOT_USERNAME}")
    print("="*70 + "\n")

    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

    print("🚀 Запускаю Safari...")
    print("⚠️  ВАЖНО: Для первого запуска нужно:")
    print("   1. Открыть Safari → Настройки → Дополнения")
    print("   2. Включить 'Показывать меню «Разработка»'")
    print("   3. Разработка → Разрешить удалённую автоматизацию")
    print()

    try:
        # Настройки Safari
        options = SafariOptions()

        # Запускаем Safari
        driver = webdriver.Safari(options=options)
        driver.set_window_size(1280, 800)

        print("✅ Safari запущен")

        # Открываем Telegram Web
        print("\n📱 Открываю Telegram Web...")
        driver.get('https://web.telegram.org/k/')
        time.sleep(5)

        driver.save_screenshot(f'{SCREENSHOTS_DIR}/safari_01_telegram.png')
        print(f"✅ Telegram Web открыт")
        print(f"   URL: {driver.current_url}")
        print(f"   Скриншот: {SCREENSHOTS_DIR}/safari_01_telegram.png")

        # Проверяем страницу
        print("\n🔍 Анализ страницы...")
        page_source = driver.page_source

        if 'Sign in to Telegram' in page_source or 'Log in to Telegram' in page_source:
            print("📱 Требуется авторизация")
            print("\n💡 ИНСТРУКЦИЯ ПО АВТОРИЗАЦИИ:")
            print("   1. Отсканируй QR-код камерой телефона через Telegram")
            print("   2. Или нажми 'LOG IN BY PHONE NUMBER'")
            print("   3. После авторизации продолжи в этом окне")

            driver.save_screenshot(f'{SCREENSHOTS_DIR}/safari_02_login.png')
            print(f"   Скриншот: {SCREENSHOTS_DIR}/safari_02_login.png")

            # Ждем авторизации
            print("\n⏳ Ожидание авторизации (5 минут)...")
            print("   Авторизуйся в браузере, скрипт продолжит автоматически")

            max_wait = 300  # 5 минут
            start = time.time()

            while time.time() - start < max_wait:
                time.sleep(5)

                # Проверяем авторизацию
                page = driver.page_source
                if 'Sign in to Telegram' not in page and 'Log in to Telegram' not in page:
                    print("\n✅ Авторизация успешна!")
                    break

                remaining = int(max_wait - (time.time() - start))
                print(f"   Осталось: {remaining} сек", end='\r')
            else:
                print("\n❌ Время ожидания истекло")
                print("   Перезапусти скрипт после авторизации")
                return

        else:
            print("✅ Уже авторизован")

        # Скриншот после авторизации
        driver.save_screenshot(f'{SCREENSHOTS_DIR}/safari_03_logged_in.png')
        print(f"   Скриншот: {SCREENSHOTS_DIR}/safari_03_logged_in.png")

        # Поиск бота
        print("\n🔍 Поиск бота...")
        time.sleep(3)

        print("💡 Найди бота вручную:")
        print(f"   1. В поиске введи: @{BOT_USERNAME}")
        print("   2. Открой чат с ботом")
        print("   3. Нажми Enter в терминале когда будешь готов...")

        input()

        # Тестирование команд
        print("\n🧪 ТЕСТИРОВАНИЕ КОМАНД")
        print("="*70)

        print("\n💡 Сейчас я буду отправлять команды боту через браузер")
        print("   Ты увидишь это в реальном времени")

        # Находим поле ввода
        input_selectors = [
            '[contenteditable="true"]',
            '.input-message-input',
            'div[class*="input"]',
        ]

        message_input = None
        for selector in input_selectors:
            try:
                message_input = driver.find_element(By.CSS_SELECTOR, selector)
                if message_input:
                    print(f"\n✅ Поле ввода найдено: {selector}")
                    break
            except:
                continue

        if not message_input:
            print("\n⚠️  Автоматический ввод не работает")
            print("   Протестируй команды вручную:")
            print("   • /start - должны появиться 4 inline кнопки")
            print("   • /help - справка")
            print("   • /stats - статистика")
            print("   • /plan - план тренировок")
            print("   • /calendar - экспорт в календарь (ICS файл)")
            print("\n   Также проверь все inline кнопки")
            input("\n   Нажми Enter когда закончишь тестирование...")
        else:
            # Отправляем /start
            print("\n📝 Отправляю /start...")
            message_input.click()
            time.sleep(0.5)

            message_input.send_keys('/start')
            time.sleep(0.5)

            message_input.send_keys(Keys.ENTER)
            time.sleep(3)

            driver.save_screenshot(f'{SCREENSHOTS_DIR}/safari_04_start.png')
            print(f"✅ Команда /start отправлена")
            print(f"   Скриншот: {SCREENSHOTS_DIR}/safari_04_start.png")

            # Проверяем кнопки
            buttons = driver.find_elements(By.CSS_SELECTOR, 'button')
            print(f"   Найдено кнопок на странице: {len(buttons)}")

            # Отправляем /help
            print("\n📝 Отправляю /help...")
            message_input.click()
            message_input.send_keys('/help')
            message_input.send_keys(Keys.ENTER)
            time.sleep(3)

            driver.save_screenshot(f'{SCREENSHOTS_DIR}/safari_05_help.png')
            print(f"✅ Команда /help отправлена")
            print(f"   Скриншот: {SCREENSHOTS_DIR}/safari_05_help.png")

            print("\n💡 Продолжи ручное тестирование:")
            print("   • Проверь все inline кнопки")
            print("   • Протестируй /stats, /plan, /calendar")
            print("   • Убедись что сообщения форматируются правильно")
            input("\n   Нажми Enter когда закончишь...")

        # Итог
        print("\n" + "="*70)
        print("📊 ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
        print("="*70)
        print(f"✅ Скриншоты сохранены: {SCREENSHOTS_DIR}")
        print("✅ Браузерное тестирование выполнено")
        print("\n💡 Все скриншоты можно посмотреть в папке screenshots/")
        print("="*70 + "\n")

        print("Закрываю браузер через 10 секунд...")
        time.sleep(10)

    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        print("\n💡 РЕШЕНИЕ:")
        print("   1. Открой Safari")
        print("   2. Настройки → Дополнения → Включи 'Показывать меню Разработка'")
        print("   3. Разработка → Разрешить удалённую автоматизацию")
        print("   4. Перезапусти скрипт")

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
