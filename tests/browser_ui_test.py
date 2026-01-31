#!/usr/bin/env python3
"""
Браузерное тестирование Telegram бота через pyppeteer
Эмулирует реальные действия пользователя в браузере
"""

import asyncio
import os
from datetime import datetime

from pyppeteer import launch

BOT_USERNAME = "training_dag_run_bot"
SCREENSHOTS_DIR = "/Users/noor/Documents/Obsidian Vault/Бот тренера/screenshots"

async def main():
    print("\n" + "="*70)
    print("🌐 БРАУЗЕРНОЕ ТЕСТИРОВАНИЕ БОТА")
    print("="*70)
    print(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Метод: Pyppeteer + Chromium")
    print(f"Бот: @{BOT_USERNAME}")
    print("="*70 + "\n")

    # Создаем папку для скриншотов
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

    # Запускаем браузер
    print("🚀 Запускаю браузер Chromium...")
    browser = await launch(
        headless=True,  # Без графического интерфейса
        args=[
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu'
        ]
    )

    try:
        page = await browser.newPage()
        await page.setViewport({'width': 1280, 'height': 800})

        print("✅ Браузер запущен")

        # Переходим на Telegram Web
        print("\n" + "="*70)
        print("🧪 ТЕСТ 1: Открываю Telegram Web")
        print("="*70)

        await page.goto('https://web.telegram.org/k/', {'waitUntil': 'networkidle0', 'timeout': 30000})
        await page.screenshot({'path': f'{SCREENSHOTS_DIR}/01_telegram_web_loaded.png'})
        print("✅ Telegram Web открыт")
        print(f"   Скриншот: {SCREENSHOTS_DIR}/01_telegram_web_loaded.png")

        # Проверяем наличие формы авторизации
        print("\n" + "="*70)
        print("🧪 ТЕСТ 2: Проверяю интерфейс авторизации")
        print("="*70)

        # Ждем загрузки страницы
        await asyncio.sleep(3)

        # Проверяем что видим - форму логина или чат
        page_content = await page.content()

        if 'Sign in to Telegram' in page_content or 'login' in page_content.lower():
            print("📱 Обнаружена форма авторизации")
            print("   Требуется ручной вход в Telegram Web")
            await page.screenshot({'path': f'{SCREENSHOTS_DIR}/02_login_form.png'})
            print(f"   Скриншот: {SCREENSHOTS_DIR}/02_login_form.png")

            print("\n⚠️  ДЛЯ ПРОДОЛЖЕНИЯ ТЕСТИРОВАНИЯ:")
            print("   1. Открой браузер вручную: https://web.telegram.org/k/")
            print("   2. Авторизуйся через телефон")
            print("   3. Сохрани сессию")
            print("   4. Перезапусти этот скрипт")

        else:
            print("✅ Страница загружена, проверяю интерфейс чата")

            # Получаем заголовок страницы
            title = await page.title()
            print(f"   Заголовок: {title}")

            # Проверяем основные элементы интерфейса
            print("\n" + "="*70)
            print("🧪 ТЕСТ 3: Анализирую элементы интерфейса")
            print("="*70)

            # Ищем поле поиска
            search_selectors = [
                'input[type="text"]',
                '.search-input',
                '[placeholder*="Search"]',
                '[placeholder*="Поиск"]'
            ]

            search_found = False
            for selector in search_selectors:
                try:
                    element = await page.querySelector(selector)
                    if element:
                        print(f"✅ Найдено поле поиска: {selector}")
                        search_found = True
                        break
                except Exception:
                    continue

            if not search_found:
                print("⚠️  Поле поиска не найдено автоматически")

            # Ищем список чатов
            chat_selectors = [
                '.chatlist',
                '.chat-list',
                '[class*="chat"]',
                '[class*="dialog"]'
            ]

            chats_found = False
            for selector in chat_selectors:
                try:
                    element = await page.querySelector(selector)
                    if element:
                        print(f"✅ Найден список чатов: {selector}")
                        chats_found = True
                        break
                except Exception:
                    continue

            if not chats_found:
                print("⚠️  Список чатов не найден автоматически")

            await page.screenshot({'path': f'{SCREENSHOTS_DIR}/03_interface_analysis.png'})
            print(f"   Скриншот: {SCREENSHOTS_DIR}/03_interface_analysis.png")

        # Итоговый отчет
        print("\n" + "="*70)
        print("📊 ИТОГОВЫЙ ОТЧЁТ")
        print("="*70)
        print("✅ Браузер работает корректно")
        print("✅ Telegram Web доступен")
        print("✅ Скриншоты сохранены в:", SCREENSHOTS_DIR)
        print("\n💡 СЛЕДУЮЩИЕ ШАГИ:")
        print("   1. Проверь скриншоты чтобы увидеть что отображается")
        print("   2. Для полного тестирования нужна авторизация в Telegram")
        print("   3. После авторизации можно протестировать бота через UI")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        await page.screenshot({'path': f'{SCREENSHOTS_DIR}/error.png'})
        print(f"   Скриншот ошибки: {SCREENSHOTS_DIR}/error.png")
        raise

    finally:
        await browser.close()
        print("🔒 Браузер закрыт")

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
