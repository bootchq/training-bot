"""
Настоящее браузерное тестирование Telegram Web через Playwright

ВНИМАНИЕ: Требует ручную авторизацию при первом запуске:
1. Скрипт откроет браузер с Telegram Web
2. Введи свой номер телефона
3. Введи код из SMS
4. После авторизации скрипт автоматически протестирует бота
"""
import asyncio
from playwright.async_api import async_playwright
import os


async def test_telegram_web_bot():
    """Тестирование бота через Telegram Web"""

    print("=" * 70)
    print("🌐 ЗАПУСК БРАУЗЕРНОГО ТЕСТИРОВАНИЯ TELEGRAM WEB")
    print("=" * 70)

    # Имя бота из переменных окружения или хардкод
    BOT_USERNAME = "training_dag_run_bot"  # Твой бот

    async with async_playwright() as p:
        print("\n🚀 Запуск браузера Chromium...")

        # Запускаем браузер в headless режиме (без окна, но работает автоматически)
        browser = await p.chromium.launch(
            headless=True,  # Без визуального окна (для совместимости с окружением)
            slow_mo=500  # Немного замедляем действия
        )

        # Создаём контекст с сохранением сессии
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 800},
            # Сохраняем сессию для повторных запусков
            storage_state='telegram_session.json' if os.path.exists('telegram_session.json') else None
        )

        page = await context.new_page()

        print("📱 Открываем Telegram Web...")
        await page.goto('https://web.telegram.org/k/')

        # Ждём загрузки
        await asyncio.sleep(5)

        # Проверяем авторизацию
        print("\n🔐 Проверка авторизации...")

        try:
            # Если видим форму авторизации - нужна ручная авторизация
            login_form = await page.query_selector('input[type="tel"]')

            if login_form:
                print("\n" + "=" * 70)
                print("⚠️ ТРЕБУЕТСЯ АВТОРИЗАЦИЯ")
                print("=" * 70)
                print("\n📞 ИНСТРУКЦИЯ:")
                print("1. В открывшемся браузере введи свой номер телефона")
                print("2. Нажми Next")
                print("3. Введи код из SMS")
                print("4. Если есть 2FA - введи пароль")
                print("5. После успешного входа нажми Enter в терминале\n")

                input("Нажми Enter когда войдёшь в Telegram Web...")

                # Сохраняем сессию для следующих запусков
                await context.storage_state(path='telegram_session.json')
                print("✅ Сессия сохранена в telegram_session.json")

        except Exception as e:
            print(f"ℹ️ Похоже уже авторизован или другой layout: {e}")

        # Ищем бота
        print(f"\n🔍 Поиск бота @{BOT_USERNAME}...")

        # Кликаем на поиск
        try:
            search_button = await page.query_selector('button.btn-icon.rp[title="Search"]') or \
                          await page.query_selector('[placeholder="Search"]') or \
                          await page.query_selector('input.input-search')

            if search_button:
                await search_button.click()
                await asyncio.sleep(1)

                # Вводим имя бота
                await page.keyboard.type(f'@{BOT_USERNAME}')
                await asyncio.sleep(2)

                # Нажимаем Enter или кликаем на первый результат
                await page.keyboard.press('Enter')
                await asyncio.sleep(3)

                print(f"✅ Открыт чат с @{BOT_USERNAME}")

            else:
                print("⚠️ Не найдена кнопка поиска, попробуем напрямую...")
                # Альтернативный путь - прямая ссылка
                await page.goto(f'https://web.telegram.org/k/#{BOT_USERNAME}')
                await asyncio.sleep(3)

        except Exception as e:
            print(f"⚠️ Ошибка поиска: {e}")
            print("Попробуй вручную открыть чат с ботом в браузере")
            input("Нажми Enter когда откроешь чат...")

        # ТЕСТИРОВАНИЕ БОТА
        print("\n" + "=" * 70)
        print("🧪 НАЧАЛО ТЕСТИРОВАНИЯ БОТА")
        print("=" * 70)

        test_results = []

        # Тест 1: Команда /start
        print("\n🧪 Тест 1: Отправка /start")
        try:
            # Находим поле ввода
            input_field = await page.query_selector('.input-message-input') or \
                         await page.query_selector('[contenteditable="true"]') or \
                         await page.query_selector('div[dir="auto"][contenteditable]')

            if input_field:
                await input_field.click()
                await page.keyboard.type('/start')
                await asyncio.sleep(1)
                await page.keyboard.press('Enter')
                await asyncio.sleep(3)

                print("✅ Команда /start отправлена")
                test_results.append(("Отправка /start", True))

                # Проверяем наличие inline кнопок
                buttons = await page.query_selector_all('button.reply-markup-button')

                if buttons:
                    print(f"✅ Найдено {len(buttons)} inline кнопок:")
                    for i, btn in enumerate(buttons[:4]):  # Первые 4 кнопки
                        btn_text = await btn.inner_text()
                        print(f"   • {btn_text}")
                    test_results.append(("Inline кнопки присутствуют", True))
                else:
                    print("⚠️ Inline кнопки не найдены")
                    test_results.append(("Inline кнопки присутствуют", False))

            else:
                print("❌ Не найдено поле ввода")
                test_results.append(("Отправка /start", False))

        except Exception as e:
            print(f"❌ Ошибка при отправке /start: {e}")
            test_results.append(("Отправка /start", False))

        # Тест 2: Нажатие inline кнопки "Статистика"
        print("\n🧪 Тест 2: Нажатие кнопки 'Статистика'")
        try:
            # Ищем кнопку со статистикой
            buttons = await page.query_selector_all('button.reply-markup-button')

            stats_button = None
            for btn in buttons:
                text = await btn.inner_text()
                if 'Статистика' in text or '📊' in text:
                    stats_button = btn
                    break

            if stats_button:
                await stats_button.click()
                await asyncio.sleep(3)

                print("✅ Кнопка 'Статистика' нажата")
                test_results.append(("Нажатие кнопки Статистика", True))

                # Проверяем появление сообщения со статистикой
                messages = await page.query_selector_all('.message')
                if messages:
                    last_msg = messages[-1]
                    msg_text = await last_msg.inner_text()
                    if 'Статистика' in msg_text or 'тренировок' in msg_text.lower():
                        print("✅ Получен ответ со статистикой")
                        test_results.append(("Ответ со статистикой", True))
                    else:
                        print(f"⚠️ Получен ответ, но не похож на статистику: {msg_text[:100]}")
                        test_results.append(("Ответ со статистикой", False))

            else:
                print("❌ Кнопка 'Статистика' не найдена")
                test_results.append(("Нажатие кнопки Статистика", False))

        except Exception as e:
            print(f"❌ Ошибка при нажатии кнопки: {e}")
            test_results.append(("Нажатие кнопки Статистика", False))

        # Тест 3: Команда /help
        print("\n🧪 Тест 3: Отправка /help")
        try:
            input_field = await page.query_selector('.input-message-input') or \
                         await page.query_selector('[contenteditable="true"]')

            if input_field:
                await input_field.click()
                # Очищаем поле
                await page.keyboard.press('Control+A')
                await page.keyboard.press('Backspace')
                await asyncio.sleep(0.5)

                await page.keyboard.type('/help')
                await asyncio.sleep(1)
                await page.keyboard.press('Enter')
                await asyncio.sleep(3)

                print("✅ Команда /help отправлена")
                test_results.append(("Отправка /help", True))

                # Проверяем ответ
                messages = await page.query_selector_all('.message')
                if messages:
                    last_msg = messages[-1]
                    msg_text = await last_msg.inner_text()
                    if 'команды' in msg_text.lower() or 'help' in msg_text.lower():
                        print("✅ Получен ответ с командами")
                        test_results.append(("Ответ с командами", True))
                    else:
                        print(f"⚠️ Получен ответ: {msg_text[:100]}")
                        test_results.append(("Ответ с командами", False))

            else:
                print("❌ Не найдено поле ввода")
                test_results.append(("Отправка /help", False))

        except Exception as e:
            print(f"❌ Ошибка при отправке /help: {e}")
            test_results.append(("Отправка /help", False))

        # ИТОГОВЫЙ ОТЧЁТ
        print("\n" + "=" * 70)
        print("📊 ИТОГОВЫЙ ОТЧЁТ БРАУЗЕРНОГО ТЕСТИРОВАНИЯ")
        print("=" * 70)

        passed = sum(1 for _, result in test_results if result)
        total = len(test_results)

        print(f"\n✅ Успешно: {passed}/{total}")
        print(f"❌ Провалено: {total - passed}/{total}")
        print(f"📈 Процент успеха: {(passed/total*100):.1f}%\n")

        print("Детали:")
        print("-" * 70)
        for test_name, result in test_results:
            status = "✅" if result else "❌"
            print(f"{status} {test_name}")

        print("=" * 70)

        if passed == total:
            print("\n🎉 ВСЕ БРАУЗЕРНЫЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
        else:
            print(f"\n⚠️ Некоторые тесты провалились. Проверь логи выше.")

        print("\n⏸️  Браузер останется открытым для ручной проверки")
        print("Нажми Enter для завершения и закрытия браузера...")
        input()

        # Сохраняем финальное состояние сессии
        await context.storage_state(path='telegram_session.json')

        await browser.close()

        print("\n✅ Тестирование завершено")


if __name__ == "__main__":
    asyncio.run(test_telegram_web_bot())
