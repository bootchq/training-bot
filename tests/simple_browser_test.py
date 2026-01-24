"""
Упрощенная симуляция браузерного тестирования через Bot API
Использует только requests - не требует установки telegram библиотеки
"""
import os
import json
import time
from datetime import datetime

try:
    import requests
except ImportError:
    print("❌ Требуется requests: pip3 install requests --user")
    exit(1)

# Загружаем токен
def load_token():
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith('TELEGRAM_BOT_TOKEN='):
                    return line.split('=', 1)[1].strip().strip('"\'')
    return os.getenv('TELEGRAM_BOT_TOKEN')


class SimpleBotTester:
    """Упрощенный тестер через Bot API"""

    def __init__(self, bot_token):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.test_results = []

    def api_call(self, method, **params):
        """Вызов Bot API"""
        url = f"{self.base_url}/{method}"
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ API Error: {e}")
            return None

    def test_bot_info(self):
        """Тест 1: Получение информации о боте"""
        print("\n" + "="*70)
        print("🧪 ТЕСТ 1: Информация о боте")
        print("="*70)

        result = self.api_call('getMe')

        if result and result.get('ok'):
            bot = result['result']
            print(f"\n✅ Бот найден:")
            print(f"   Имя: {bot.get('first_name')}")
            print(f"   Username: @{bot.get('username')}")
            print(f"   ID: {bot.get('id')}")

            self.test_results.append(("Доступность бота", True, f"@{bot.get('username')}"))
            return True
        else:
            print(f"\n❌ Бот недоступен")
            self.test_results.append(("Доступность бота", False, "API error"))
            return False

    def test_commands(self):
        """Тест 2: Проверка зарегистрированных команд"""
        print("\n" + "="*70)
        print("🧪 ТЕСТ 2: Зарегистрированные команды")
        print("="*70)

        result = self.api_call('getMyCommands')

        if result and result.get('ok'):
            commands = result['result']
            print(f"\n✅ Найдено команд: {len(commands)}")

            for cmd in commands:
                print(f"   /{cmd['command']} - {cmd['description']}")

            expected = ['start', 'help', 'sync', 'stats', 'plan', 'calendar']
            registered = [cmd['command'] for cmd in commands]
            missing = [c for c in expected if c not in registered]

            if missing:
                print(f"\n⚠️  Отсутствуют: {missing}")
                self.test_results.append(("Команды зарегистрированы", False, f"Отсутствуют: {missing}"))
                return False
            else:
                self.test_results.append(("Команды зарегистрированы", True, f"{len(commands)} команд"))
                return True
        else:
            print(f"\n❌ Не удалось получить команды")
            self.test_results.append(("Команды зарегистрированы", False, "API error"))
            return False

    def test_webhook_status(self):
        """Тест 3: Проверка webhook/polling"""
        print("\n" + "="*70)
        print("🧪 ТЕСТ 3: Режим работы бота")
        print("="*70)

        result = self.api_call('getWebhookInfo')

        if result and result.get('ok'):
            info = result['result']
            url = info.get('url')

            if url:
                print(f"\n📡 Режим: WEBHOOK")
                print(f"   URL: {url}")
                print(f"   Pending updates: {info.get('pending_update_count', 0)}")
                mode = "webhook"
            else:
                print(f"\n📡 Режим: POLLING")
                mode = "polling"

            self.test_results.append(("Режим работы", True, mode))
            return True
        else:
            print(f"\n❌ Не удалось получить webhook info")
            self.test_results.append(("Режим работы", False, "API error"))
            return False

    def send_test_message(self, chat_id, text):
        """Тест 4: Отправка тестового сообщения"""
        print("\n" + "="*70)
        print(f"🧪 ТЕСТ 4: Отправка сообщения: {text}")
        print("="*70)

        result = self.api_call('sendMessage', chat_id=chat_id, text=text)

        if result and result.get('ok'):
            msg = result['result']
            print(f"\n✅ Сообщение отправлено")
            print(f"   Message ID: {msg.get('message_id')}")
            print(f"   Чат: {msg['chat'].get('id')}")

            self.test_results.append((f"Отправка '{text}'", True, f"msg_id: {msg.get('message_id')}"))
            return True
        else:
            error = result.get('description', 'Unknown') if result else 'No response'
            print(f"\n❌ Ошибка отправки: {error}")
            self.test_results.append((f"Отправка '{text}'", False, error))
            return False

    def get_updates(self):
        """Получение последних обновлений"""
        print("\n" + "="*70)
        print("🧪 ТЕСТ 5: Получение обновлений (последние сообщения)")
        print("="*70)

        result = self.api_call('getUpdates', limit=5, timeout=10)

        if result and result.get('ok'):
            updates = result['result']
            print(f"\n✅ Получено обновлений: {len(updates)}")

            if updates:
                print("\nПоследние сообщения:")
                for upd in updates[-3:]:  # Последние 3
                    if 'message' in upd:
                        msg = upd['message']
                        text = msg.get('text', '(файл/медиа)')[:50]
                        user = msg.get('from', {}).get('first_name', 'Unknown')
                        print(f"   [{user}]: {text}")

            self.test_results.append(("Получение updates", True, f"{len(updates)} updates"))
            return updates
        else:
            print(f"\n❌ Не удалось получить updates")
            self.test_results.append(("Получение updates", False, "API error"))
            return []

    def print_summary(self):
        """Итоговый отчёт"""
        print("\n" + "="*70)
        print("📊 ИТОГОВЫЙ ОТЧЁТ БРАУЗЕРНОЙ СИМУЛЯЦИИ")
        print("="*70)

        passed = sum(1 for _, result, _ in self.test_results if result)
        total = len(self.test_results)

        print(f"\n✅ Успешно: {passed}/{total}")
        print(f"❌ Провалено: {total - passed}/{total}")
        print(f"📈 Процент успеха: {(passed/total*100):.1f}%\n")

        print("Детали:")
        print("-" * 70)

        for test_name, result, details in self.test_results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status:10} | {test_name:35} | {details}")

        print("=" * 70)

        if total - passed > 0:
            print(f"\n⚠️ ТРЕБУЕТСЯ ВНИМАНИЕ:")
            for test_name, result, details in self.test_results:
                if not result:
                    print(f"  • {test_name}: {details}")
        else:
            print(f"\n🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")

    def run_all_tests(self, test_chat_id=None):
        """Запуск всех тестов"""
        print("\n🚀 ЗАПУСК БРАУЗЕРНОЙ СИМУЛЯЦИИ ЧЕРЕЗ BOT API")
        print("="*70)
        print(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Метод: Прямые вызовы Bot API (requests)")
        print("="*70)

        # Тесты, которые не требуют chat_id
        self.test_bot_info()
        time.sleep(1)

        self.test_commands()
        time.sleep(1)

        self.test_webhook_status()
        time.sleep(1)

        # Если есть chat_id - отправляем тестовое сообщение
        if test_chat_id:
            self.send_test_message(test_chat_id, "/start")
            time.sleep(2)

        self.get_updates()

        self.print_summary()

        return sum(1 for _, result, _ in self.test_results if result) == len(self.test_results)


def main():
    """Главная функция"""
    token = load_token()

    if not token:
        print("❌ ОШИБКА: TELEGRAM_BOT_TOKEN не найден")
        print("\nСоздай .env файл с:")
        print('TELEGRAM_BOT_TOKEN="your_bot_token_here"')
        return 1

    tester = SimpleBotTester(token)

    # Спрашиваем chat_id опционально
    print("\n" + "="*70)
    print("ОПЦИОНАЛЬНО: Тестовая отправка сообщения")
    print("="*70)
    print("\nЧтобы протестировать отправку сообщений, введи свой Telegram ID")
    print("(Узнай у бота @userinfobot или пропусти, нажав Enter)\n")

    try:
        chat_id_input = input("Telegram ID (или Enter для пропуска): ").strip()
        chat_id = int(chat_id_input) if chat_id_input else None
    except (ValueError, KeyboardInterrupt):
        chat_id = None
        print("\n⏭️  Пропускаем тесты с отправкой сообщений")

    success = tester.run_all_tests(chat_id)

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
