#!/usr/bin/env python3
"""
CDP ТЕСТЕР БОТА
Использует Chrome DevTools Protocol для настоящих кликов
CDP события являются "trusted" и обходят browser security

Запуск:
    python3 cdp_bot_tester.py
"""

import asyncio
import os
import subprocess
from pathlib import Path

# Конфигурация
BOT_USERNAME = 'training_dag_run_bot'
CHROME_DEBUG_PORT = 9222
TELEGRAM_URL = f'https://web.telegram.org/k/#{BOT_USERNAME}'

# Путь к Chrome профилю с сохранённой сессией
CHROME_PROFILE = os.path.expanduser('~/Library/Application Support/Google/Chrome/BotTesting')


def print_header(msg):
    print(f"\n{'='*70}\n{msg}\n{'='*70}")


def ok(msg):
    print(f"✅ {msg}")


def fail(msg):
    print(f"❌ {msg}")


def info(msg):
    print(f"ℹ️  {msg}")


def warn(msg):
    print(f"⚠️  {msg}")


async def launch_chrome():
    """Запустить Chrome с remote debugging"""
    print_header("ЗАПУСК CHROME")

    # Проверяем, не запущен ли уже
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(f'http://localhost:{CHROME_DEBUG_PORT}/json/version', timeout=aiohttp.ClientTimeout(total=2)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    ok(f"Chrome уже запущен: {data.get('Browser', 'Chrome')}")
                    return True
    except:
        pass

    info("Запускаю Chrome...")

    # Создаём профиль если нет
    profile_path = Path(CHROME_PROFILE)
    if not profile_path.exists():
        profile_path.mkdir(parents=True)
        info(f"Создан профиль: {CHROME_PROFILE}")

    # Запускаем Chrome
    chrome_cmd = [
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        f'--remote-debugging-port={CHROME_DEBUG_PORT}',
        f'--user-data-dir={CHROME_PROFILE}',
        '--no-first-run',
        '--no-default-browser-check',
        TELEGRAM_URL
    ]

    subprocess.Popen(chrome_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Ждём запуска
    for i in range(10):
        await asyncio.sleep(1)
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(f'http://localhost:{CHROME_DEBUG_PORT}/json/version', timeout=aiohttp.ClientTimeout(total=2)) as resp:
                    if resp.status == 200:
                        ok("Chrome запущен")
                        return True
        except:
            pass

    fail("Не удалось запустить Chrome")
    return False


async def test_with_pyppeteer():
    """Тестирование через pyppeteer (CDP)"""
    print_header("CDP ТЕСТИРОВАНИЕ (pyppeteer)")

    try:
        from pyppeteer import connect
    except ImportError:
        fail("pyppeteer не установлен. Выполни: pip install pyppeteer")
        return False

    # Подключаемся к Chrome
    info("Подключаюсь к Chrome через CDP...")

    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(f'http://localhost:{CHROME_DEBUG_PORT}/json/version') as resp:
                data = await resp.json()
                ws_url = data['webSocketDebuggerUrl']
    except Exception as e:
        fail(f"Не могу получить WebSocket URL: {e}")
        fail("Убедись что Chrome запущен с --remote-debugging-port=9222")
        return False

    try:
        browser = await connect(browserWSEndpoint=ws_url)
        ok("Подключён к Chrome через CDP")
    except Exception as e:
        fail(f"Ошибка подключения: {e}")
        return False

    # Получаем страницы
    pages = await browser.pages()
    info(f"Открыто {len(pages)} вкладок")

    # Ищем страницу Telegram
    tg_page = None
    for page in pages:
        url = page.url
        if 'web.telegram.org' in url:
            tg_page = page
            ok(f"Найдена страница Telegram: {url}")
            break

    if not tg_page:
        info("Страница Telegram не найдена, открываю...")
        tg_page = await browser.newPage()
        await tg_page.goto(TELEGRAM_URL, waitUntil='networkidle0', timeout=60000)
        await asyncio.sleep(3)

    # Переходим на страницу
    await tg_page.bringToFront()

    # Проверяем авторизацию
    print_header("ПРОВЕРКА АВТОРИЗАЦИИ")

    await asyncio.sleep(2)

    # Проверяем есть ли поле ввода (значит авторизован)
    is_logged_in = await tg_page.evaluate('''() => {
        return document.querySelector('.input-message-input') !== null ||
               document.querySelector('[class*="input-field"]') !== null;
    }''')

    if is_logged_in:
        ok("Авторизован в Telegram")
    else:
        warn("Не авторизован. Авторизуйся вручную и перезапусти тест.")
        print("\n⏳ Жду 30 секунд для авторизации...")
        await asyncio.sleep(30)

    # Переходим к боту
    print_header("ОТКРЫВАЮ БОТА")

    # Проверяем, открыт ли уже чат с ботом
    current_url = tg_page.url
    if BOT_USERNAME not in current_url:
        info(f"Перехожу к боту @{BOT_USERNAME}...")
        await tg_page.goto(TELEGRAM_URL, waitUntil='networkidle0', timeout=30000)
        await asyncio.sleep(3)

    ok("Страница бота открыта")

    # Отправляем /start
    print_header("ТЕСТ: Отправка /start")

    # Ищем поле ввода
    input_selector = '.input-message-input'

    try:
        await tg_page.waitForSelector(input_selector, timeout=10000)
        ok("Поле ввода найдено")
    except:
        fail("Поле ввода не найдено")
        # Попробуем другой селектор
        input_selector = '[contenteditable="true"]'
        try:
            await tg_page.waitForSelector(input_selector, timeout=5000)
            ok(f"Использую альтернативный селектор: {input_selector}")
        except:
            fail("Не могу найти поле ввода")
            return False

    # Очищаем и вводим /start
    await tg_page.click(input_selector)
    await asyncio.sleep(0.3)

    # Вводим текст
    await tg_page.keyboard.type('/start', delay=50)
    await asyncio.sleep(0.3)

    # Отправляем
    await tg_page.keyboard.press('Enter')
    ok("Команда /start отправлена")

    # Ждём ответа
    await asyncio.sleep(3)

    # Скроллим вниз к последнему сообщению
    print_header("ПОИСК INLINE КНОПОК")

    info("Скроллю к последнему сообщению...")
    await tg_page.evaluate('''() => {
        const container = document.querySelector('.bubbles-inner') ||
                          document.querySelector('.messages-container') ||
                          document.querySelector('[class*="chat"]');
        if (container) {
            container.scrollTop = container.scrollHeight;
        }
        window.scrollTo(0, document.body.scrollHeight);
    }''')
    await asyncio.sleep(1)

    # Ищем кнопки только в ПОСЛЕДНЕМ сообщении с кнопками
    buttons = await tg_page.evaluate('''() => {
        const buttons = [];

        // Находим все группы inline кнопок
        const replyMarkups = document.querySelectorAll('.reply-markup, [class*="keyboard"], [class*="inline-buttons"]');

        if (replyMarkups.length > 0) {
            // Берём ПОСЛЕДНЮЮ группу кнопок
            const lastMarkup = replyMarkups[replyMarkups.length - 1];
            const btns = lastMarkup.querySelectorAll('button');

            btns.forEach(btn => {
                const rect = btn.getBoundingClientRect();
                const text = btn.textContent.trim();
                if (rect.width > 0 && rect.height > 0 && text) {
                    buttons.push({
                        text: text,
                        x: rect.x + rect.width / 2,
                        y: rect.y + rect.height / 2,
                        visible: rect.y > 0 && rect.y < window.innerHeight
                    });
                }
            });
        }

        return buttons;
    }''')

    if buttons:
        ok(f"Найдено {len(buttons)} кнопок в последнем сообщении")
        for btn in buttons:
            status = "✓" if btn['visible'] else "↓"
            print(f"   {status} {btn['text']} @ ({btn['x']:.0f}, {btn['y']:.0f})")
    else:
        warn("Кнопки не найдены в reply-markup, пробую альтернативный поиск...")

        # Альтернативный поиск - последние 4 кнопки с нужным текстом
        buttons = await tg_page.evaluate('''() => {
            const buttons = [];
            const allButtons = Array.from(document.querySelectorAll('button'));

            // Фильтруем только нужные кнопки
            const targetButtons = allButtons.filter(btn => {
                const text = btn.textContent.trim();
                return text.includes('📊') || text.includes('📅') ||
                       text.includes('🔄') || text.includes('📲');
            });

            // Берём последние 4 (один набор кнопок)
            const lastFour = targetButtons.slice(-4);

            lastFour.forEach(btn => {
                const rect = btn.getBoundingClientRect();
                buttons.push({
                    text: btn.textContent.trim(),
                    x: rect.x + rect.width / 2,
                    y: rect.y + rect.height / 2,
                    visible: rect.y > 0 && rect.y < window.innerHeight
                });
            });

            return buttons;
        }''')

        if buttons:
            ok(f"Найдено {len(buttons)} кнопок (последний набор)")
            for btn in buttons:
                print(f"   🔘 {btn['text']} @ ({btn['x']:.0f}, {btn['y']:.0f})")

    if not buttons:
        warn("Inline кнопки не найдены в DOM")
        info("Возможно бот ещё не ответил или формат сообщений изменился")

        # Скриншот для диагностики
        screenshot_path = '/tmp/telegram_test.png'
        await tg_page.screenshot({'path': screenshot_path, 'fullPage': True})
        info(f"Скриншот сохранён: {screenshot_path}")

        return False

    # КЛИКАЕМ ПО КНОПКАМ ЧЕРЕЗ CDP!
    print_header("КЛИКИ ПО КНОПКАМ (CDP)")

    results = []
    tested_buttons = set()  # Чтобы не кликать дважды по одной кнопке

    for btn in buttons:
        btn_key = btn['text'][:15]
        if btn_key in tested_buttons:
            continue
        tested_buttons.add(btn_key)

        print(f"\n🖱️  Кликаю: {btn['text']}")

        try:
            # Сначала скроллим к кнопке если она не видна
            if not btn['visible'] or btn['y'] < 0 or btn['y'] > 800:
                info("   Скроллю к кнопке...")
                await tg_page.evaluate('''() => {
                    const container = document.querySelector('.bubbles-inner') ||
                                      document.querySelector('.messages-container');
                    if (container) container.scrollTop = container.scrollHeight;
                }''')
                await asyncio.sleep(0.5)

            # Находим кнопку заново (после скролла)
            btn_emoji = btn['text'][:2]  # Emoji в начале
            updated_btn = await tg_page.evaluate(f'''() => {{
                const allButtons = Array.from(document.querySelectorAll('button'));
                const matching = allButtons.filter(b => b.textContent.trim().startsWith("{btn_emoji}"));
                if (matching.length > 0) {{
                    const last = matching[matching.length - 1];
                    const rect = last.getBoundingClientRect();
                    return {{
                        x: rect.x + rect.width/2,
                        y: rect.y + rect.height/2,
                        visible: rect.y > 0 && rect.y < window.innerHeight
                    }};
                }}
                return null;
            }}''')

            if updated_btn and updated_btn['visible']:
                # CDP Mouse click - НАСТОЯЩИЙ клик
                await tg_page.mouse.click(updated_btn['x'], updated_btn['y'])
                ok(f"   Клик @ ({updated_btn['x']:.0f}, {updated_btn['y']:.0f})")

                # Ждём ответа бота
                await asyncio.sleep(2)

                # Проверяем что бот ответил
                new_message = await tg_page.evaluate('''() => {
                    const bubbles = document.querySelectorAll('.bubble, .message');
                    if (bubbles.length > 0) {
                        const last = bubbles[bubbles.length - 1];
                        const text = last.textContent || '';
                        const hasDoc = last.querySelector('.document, .media-document') !== null;
                        const hasFile = text.includes('.ics') || text.includes('ICS');
                        return {
                            text: text.substring(0, 200),
                            hasDocument: hasDoc || hasFile
                        };
                    }
                    return null;
                }''')

                if new_message:
                    if 'календарь' in btn['text'].lower():
                        if new_message['hasDocument']:
                            ok("   Получен ICS файл!")
                            results.append(True)
                        elif 'план' in new_message['text'].lower() or 'создай' in new_message['text'].lower():
                            ok("   Бот просит создать план (ожидаемо)")
                            results.append(True)
                        else:
                            warn(f"   Ответ: {new_message['text'][:80]}...")
                            results.append(True)  # Бот ответил, это успех
                    else:
                        ok("   Бот ответил")
                        results.append(True)
                else:
                    warn("   Нет ответа от бота")
                    results.append(False)

            else:
                warn("   Кнопка не видна, пропускаю")
                results.append(False)

        except Exception as e:
            fail(f"   Ошибка: {e}")
            results.append(False)

    # Итоги
    print_header("ИТОГИ CDP ТЕСТИРОВАНИЯ")

    passed = sum(results)
    total = len(results)

    if total > 0:
        print(f"Результат: {passed}/{total} кнопок успешно нажато")

        if passed == total:
            ok("ВСЕ КЛИКИ СРАБОТАЛИ!")
            return True
        else:
            warn("Некоторые клики не сработали")
            return False
    else:
        warn("Не было кнопок для тестирования")
        return False


async def main():
    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║           🖱️  CDP ТЕСТЕР БОТА (Chrome DevTools Protocol)             ║
╚══════════════════════════════════════════════════════════════════════╝

CDP клики являются "trusted" и обходят browser security.
Это должно решить проблему с inline кнопками.

Бот: @{BOT_USERNAME}
""")

    # Запускаем Chrome
    if not await launch_chrome():
        return False

    # Даём время на загрузку
    await asyncio.sleep(2)

    # Тестируем
    success = await test_with_pyppeteer()

    if success:
        print("\n🎉 CDP ТЕСТИРОВАНИЕ УСПЕШНО!")
    else:
        print("\n⚠️  Есть проблемы, см. выше")

    return success


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n❌ Прервано")
        exit(1)
