#!/usr/bin/env python3
"""
УНИВЕРСАЛЬНЫЙ ТЕСТЕР БОТА
Один скрипт для всех видов тестирования

Режимы:
1. БАЗОВЫЙ (Bot API) - проверка что бот онлайн, команды зарегистрированы
2. ПОЛНЫЙ (Telethon) - E2E с отправкой команд и кликами по кнопкам

Запуск:
    python3 bot_tester.py          # автовыбор режима
    python3 bot_tester.py --basic   # только базовый
    python3 bot_tester.py --full    # полный (с запросом credentials)
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path


# Цвета для терминала
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def ok(msg): print(f"{Colors.GREEN}✅ {msg}{Colors.END}")
def fail(msg): print(f"{Colors.RED}❌ {msg}{Colors.END}")
def warn(msg): print(f"{Colors.YELLOW}⚠️  {msg}{Colors.END}")
def info(msg): print(f"{Colors.BLUE}ℹ️  {msg}{Colors.END}")
def header(msg): print(f"\n{Colors.BOLD}{'='*70}\n{msg}\n{'='*70}{Colors.END}")

# Пути
PROJECT_DIR = Path(__file__).parent.parent
ENV_FILE = PROJECT_DIR / '.env'
CONFIG_FILE = Path.home() / '.telegram_api_config'
SESSION_FILE = PROJECT_DIR.parent / 'telegram_test_session'

# Загрузка .env
def load_env():
    """Загрузить переменные из .env"""
    env = {}
    if ENV_FILE.exists():
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env[key] = value
    return env

ENV = load_env()
BOT_TOKEN = ENV.get('TELEGRAM_BOT_TOKEN')
BOT_USERNAME = 'training_dag_run_bot'

# ============================================================================
# БАЗОВОЕ ТЕСТИРОВАНИЕ (Bot API)
# ============================================================================

async def test_bot_api():
    """Тесты через Telegram Bot API"""
    import aiohttp

    header("БАЗОВОЕ ТЕСТИРОВАНИЕ (Bot API)")

    if not BOT_TOKEN:
        fail("TELEGRAM_BOT_TOKEN не найден в .env")
        return False

    base_url = f"https://api.telegram.org/bot{BOT_TOKEN}"
    results = []

    async with aiohttp.ClientSession() as session:
        # Тест 1: getMe - бот онлайн?
        print("\n🧪 Тест 1: Бот онлайн?")
        try:
            async with session.get(f"{base_url}/getMe") as resp:
                data = await resp.json()
                if data.get('ok'):
                    bot_info = data['result']
                    ok(f"Бот онлайн: @{bot_info['username']}")
                    ok(f"Имя: {bot_info['first_name']}")
                    results.append(True)
                else:
                    fail(f"Ошибка: {data}")
                    results.append(False)
        except Exception as e:
            fail(f"Не могу подключиться: {e}")
            results.append(False)

        # Тест 2: getMyCommands - команды зарегистрированы?
        print("\n🧪 Тест 2: Команды зарегистрированы?")
        try:
            async with session.get(f"{base_url}/getMyCommands") as resp:
                data = await resp.json()
                if data.get('ok'):
                    commands = data['result']
                    if commands:
                        ok(f"Зарегистрировано {len(commands)} команд:")
                        for cmd in commands:
                            print(f"   /{cmd['command']} - {cmd['description']}")

                        # Проверяем наличие основных команд
                        cmd_names = [c['command'] for c in commands]
                        required = ['start', 'help', 'stats', 'plan', 'sync', 'calendar']
                        missing = [c for c in required if c not in cmd_names]

                        if missing:
                            warn(f"Не хватает команд: {missing}")
                        else:
                            ok("Все основные команды на месте")

                        results.append(len(missing) == 0)
                    else:
                        warn("Команды не зарегистрированы (бот работает, но /help не покажет список)")
                        results.append(True)  # Не критично
                else:
                    fail(f"Ошибка: {data}")
                    results.append(False)
        except Exception as e:
            fail(f"Ошибка: {e}")
            results.append(False)

        # Тест 3: getWebhookInfo - режим работы
        print("\n🧪 Тест 3: Режим работы")
        try:
            async with session.get(f"{base_url}/getWebhookInfo") as resp:
                data = await resp.json()
                if data.get('ok'):
                    webhook = data['result']
                    if webhook.get('url'):
                        ok(f"Webhook: {webhook['url']}")
                        if webhook.get('pending_update_count'):
                            warn(f"Необработанных апдейтов: {webhook['pending_update_count']}")
                    else:
                        ok("Режим: Polling (локальный)")
                    results.append(True)
        except Exception as e:
            warn(f"Не могу проверить webhook: {e}")
            results.append(True)

        # Тест 4: getUpdates - последние сообщения (только для polling)
        print("\n🧪 Тест 4: Последние сообщения")
        try:
            async with session.get(f"{base_url}/getUpdates", params={'limit': 5, 'timeout': 1}) as resp:
                data = await resp.json()
                if data.get('ok'):
                    updates = data['result']
                    if updates:
                        ok(f"Получено {len(updates)} последних апдейтов")
                        for upd in updates[-3:]:
                            if 'message' in upd:
                                msg = upd['message']
                                user = msg.get('from', {}).get('first_name', 'Unknown')
                                text = msg.get('text', '(без текста)')[:50]
                                print(f"   📝 {user}: {text}")
                    else:
                        info("Нет новых сообщений")
                    results.append(True)
                elif 'Conflict' in str(data):
                    info("Polling занят (бот уже запущен)")
                    results.append(True)
                else:
                    warn(f"Не могу получить апдейты: {data}")
                    results.append(True)
        except Exception as e:
            info(f"Апдейты недоступны (бот в режиме polling): {e}")
            results.append(True)

    return all(results)


# ============================================================================
# ПОЛНОЕ ТЕСТИРОВАНИЕ (Telethon)
# ============================================================================

def get_telethon_credentials():
    """Получить или запросить Telethon credentials"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            lines = f.readlines()
            if len(lines) >= 2:
                return {
                    'api_id': int(lines[0].strip()),
                    'api_hash': lines[1].strip(),
                    'phone': lines[2].strip() if len(lines) > 2 else None
                }
    return None

def setup_telethon_credentials():
    """Интерактивная настройка credentials"""
    header("НАСТРОЙКА TELETHON")

    print("""
Для полного тестирования (с кликами по кнопкам) нужны API credentials.

📱 КАК ПОЛУЧИТЬ:
   1. Открой: https://my.telegram.org/apps
   2. Войди через номер телефона
   3. Создай приложение (название любое)
   4. Скопируй API ID и API Hash
""")

    try:
        api_id = input("API ID: ").strip()
        api_hash = input("API Hash: ").strip()
        phone = input("Номер телефона (с +): ").strip()

        # Сохраняем
        with open(CONFIG_FILE, 'w') as f:
            f.write(f"{api_id}\n{api_hash}\n{phone}\n")

        ok(f"Credentials сохранены в {CONFIG_FILE}")
        return {
            'api_id': int(api_id),
            'api_hash': api_hash,
            'phone': phone
        }
    except KeyboardInterrupt:
        print()
        warn("Отменено")
        return None


async def test_telethon():
    """Полные E2E тесты через Telethon"""
    try:
        from telethon import TelegramClient
    except ImportError:
        fail("Telethon не установлен. Выполни: pip install telethon")
        return False

    header("ПОЛНОЕ ТЕСТИРОВАНИЕ (Telethon)")

    creds = get_telethon_credentials()
    if not creds:
        creds = setup_telethon_credentials()
        if not creds:
            return False

    client = TelegramClient(str(SESSION_FILE), creds['api_id'], creds['api_hash'])
    results = []

    try:
        print("\n🔐 Подключаюсь к Telegram...")
        await client.start(phone=creds['phone'])
        ok("Подключен!")

        # Находим бота
        print(f"\n🔍 Ищу бота @{BOT_USERNAME}...")
        try:
            bot = await client.get_entity(BOT_USERNAME)
            ok(f"Бот найден: {bot.first_name}")
        except Exception as e:
            fail(f"Бот не найден: {e}")
            return False

        # Тест 1: /start
        print("\n🧪 Тест 1: Команда /start")
        await client.send_message(bot, '/start')
        await asyncio.sleep(2)

        messages = await client.get_messages(bot, limit=1)
        if messages:
            msg = messages[0]
            if msg.text:
                ok(f"Ответ получен: {msg.text[:100]}...")

                # Проверяем inline кнопки
                if msg.reply_markup:
                    buttons = []
                    for row in msg.reply_markup.rows:
                        for btn in row.buttons:
                            buttons.append(btn.text)

                    ok(f"Найдено {len(buttons)} кнопок: {buttons}")
                    results.append(True)

                    # Кликаем по каждой кнопке
                    print("\n🖱️  Кликаю по кнопкам:")
                    for row_idx, row in enumerate(msg.reply_markup.rows):
                        for btn_idx, button in enumerate(row.buttons):
                            print(f"\n   🔘 Кнопка: {button.text}")
                            try:
                                await msg.click(btn_idx)
                                await asyncio.sleep(2)

                                new_msg = (await client.get_messages(bot, limit=1))[0]

                                if new_msg.document:
                                    ok(f"      Файл: {new_msg.file.name}")
                                    if 'календарь' in button.text.lower():
                                        if new_msg.file.name.endswith('.ics'):
                                            ok("      ICS файл — OAuth исправлен!")
                                elif new_msg.text and new_msg.id != msg.id:
                                    ok(f"      Ответ: {new_msg.text[:80]}...")

                            except Exception as e:
                                warn(f"      Ошибка клика: {e}")
                else:
                    warn("Inline кнопок нет")
                    results.append(False)
            else:
                fail("Пустой ответ")
                results.append(False)
        else:
            fail("Нет ответа")
            results.append(False)

        # Тест 2: /calendar
        print("\n🧪 Тест 2: Команда /calendar")
        await client.send_message(bot, '/calendar')
        await asyncio.sleep(3)

        msg = (await client.get_messages(bot, limit=1))[0]
        if msg.document:
            ok(f"Файл получен: {msg.file.name}")
            if msg.file.name.endswith('.ics'):
                ok("ICS файл — OAuth проблема ИСПРАВЛЕНА!")
                results.append(True)
            else:
                warn("Не ICS файл")
                results.append(False)
        elif msg.text:
            if 'OAuth' in msg.text or 'авторизов' in msg.text.lower():
                fail("OAuth всё ещё используется!")
                results.append(False)
            else:
                ok(f"Ответ: {msg.text[:100]}...")
                results.append(True)

        # Тест 3: Другие команды
        for cmd in ['/help', '/stats', '/plan']:
            print(f"\n🧪 Тест: {cmd}")
            await client.send_message(bot, cmd)
            await asyncio.sleep(2)

            msg = (await client.get_messages(bot, limit=1))[0]
            if msg.text:
                ok(f"Ответ: {msg.text[:80]}...")
                results.append(True)
            else:
                warn("Нет ответа")
                results.append(False)

    except Exception as e:
        fail(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await client.disconnect()

    return all(results)


# ============================================================================
# UNIT ТЕСТЫ (логика без сети)
# ============================================================================

async def test_unit():
    """Unit тесты логики бота"""
    header("UNIT ТЕСТЫ (логика)")

    # Добавляем путь к модулям
    sys.path.insert(0, str(PROJECT_DIR / 'src'))

    try:
        from unittest.mock import AsyncMock
        from unittest.mock import Mock
        from unittest.mock import patch

        from bot.telegram_bot import TelegramTrainingBot

        bot = TelegramTrainingBot()
        results = []

        # Создаём mock update
        def make_update(text="/start", user_id=12345):
            update = Mock()
            update.effective_user = Mock()
            update.effective_user.id = user_id
            update.effective_user.first_name = "TestUser"
            update.message = Mock()
            update.message.text = text
            update.message.reply_text = AsyncMock()
            update.message.reply_document = AsyncMock()
            update.message.chat = Mock()
            update.message.chat.id = user_id
            update.callback_query = None
            return update

        def make_context():
            context = Mock()
            context.user_data = {}
            context.bot = Mock()
            context.bot.send_message = AsyncMock()
            return context

        # Тест 1: /start
        print("\n🧪 Unit тест: /start")
        update = make_update("/start")
        context = make_context()
        await bot.start(update, context)

        if update.message.reply_text.called:
            call_args = update.message.reply_text.call_args
            text = call_args[0][0] if call_args[0] else ""
            ok(f"Ответ: {text[:80]}...")

            # Проверяем inline кнопки
            if 'reply_markup' in call_args[1]:
                markup = call_args[1]['reply_markup']
                if hasattr(markup, 'inline_keyboard'):
                    buttons = [b.text for row in markup.inline_keyboard for b in row]
                    ok(f"Кнопки: {buttons}")
                    results.append(True)
                else:
                    warn("Нет inline кнопок")
                    results.append(False)
            else:
                warn("Нет reply_markup")
                results.append(False)
        else:
            fail("reply_text не вызван")
            results.append(False)

        # Тест 2: /help
        print("\n🧪 Unit тест: /help")
        update = make_update("/help")
        context = make_context()
        await bot.help_command(update, context)

        if update.message.reply_text.called:
            text = update.message.reply_text.call_args[0][0]
            ok(f"Ответ: {text[:80]}...")
            results.append(True)
        else:
            fail("Нет ответа")
            results.append(False)

        return all(results)

    except ImportError as e:
        fail(f"Не могу импортировать модули бота: {e}")
        info("Убедись что бот установлен и путь правильный")
        return False
    except Exception as e:
        fail(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================

async def main():
    """Главная функция"""
    print(f"""
{Colors.BOLD}╔══════════════════════════════════════════════════════════════════════╗
║                    🤖 ТЕСТЕР БОТА-ТРЕНЕРА                             ║
╚══════════════════════════════════════════════════════════════════════╝{Colors.END}
Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Бот: @{BOT_USERNAME}
""")

    # Парсим аргументы
    args = sys.argv[1:]

    if '--basic' in args:
        modes = ['basic']
    elif '--full' in args:
        modes = ['basic', 'telethon']
    elif '--unit' in args:
        modes = ['unit']
    else:
        # Автовыбор: базовый, telethon если есть credentials
        modes = ['basic']
        if CONFIG_FILE.exists():
            modes.append('telethon')

    results = {}

    # Запускаем тесты
    if 'basic' in modes:
        results['Bot API'] = await test_bot_api()

    if 'unit' in modes:
        results['Unit тесты'] = await test_unit()

    if 'telethon' in modes:
        results['Telethon E2E'] = await test_telethon()

    # Итоги
    header("ИТОГИ ТЕСТИРОВАНИЯ")

    all_passed = True
    for name, passed in results.items():
        status = f"{Colors.GREEN}✅ PASS{Colors.END}" if passed else f"{Colors.RED}❌ FAIL{Colors.END}"
        print(f"{status} | {name}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print(f"{Colors.GREEN}{Colors.BOLD}🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!{Colors.END}")
    else:
        print(f"{Colors.YELLOW}⚠️  Есть проблемы, см. выше{Colors.END}")

    # Подсказки
    if 'telethon' not in modes and '--full' not in args:
        print(f"""
{Colors.BLUE}💡 Для полного E2E тестирования с кликами по кнопкам:{Colors.END}
   python3 bot_tester.py --full
""")

    return all_passed


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n❌ Прервано")
        sys.exit(1)
