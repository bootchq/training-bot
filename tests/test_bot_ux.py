"""
Автоматизированный UX тест бота
Симулирует действия пользователя и проверяет ответы бота
"""
import asyncio
import os
import sys

# Добавляем путь к src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import AsyncMock
from unittest.mock import Mock

from telegram import CallbackQuery
from telegram import Chat
from telegram import Message
from telegram import Update
from telegram import User
from telegram.ext import ContextTypes

from src.bot.telegram_bot import TrainingBot
from src.database.db import db


class BotTester:
    """Тестер UX бота"""

    def __init__(self):
        """Инициализация тестера"""
        self.bot = TrainingBot()
        self.test_user_id = 999999999  # Тестовый Telegram ID
        self.results = []

    def _create_mock_update(self, text: str = None, callback_data: str = None):
        """Создать mock Update объект"""
        # Mock user
        user = Mock(spec=User)
        user.id = self.test_user_id
        user.first_name = "Test"
        user.username = "testuser"

        # Mock chat
        chat = Mock(spec=Chat)
        chat.id = self.test_user_id

        # Mock message
        message = AsyncMock(spec=Message)
        message.chat = chat
        message.from_user = user
        message.text = text
        message.reply_text = AsyncMock()
        message.delete = AsyncMock()

        # Mock update
        update = Mock(spec=Update)
        update.effective_user = user
        update.message = message

        # Если это callback query
        if callback_data:
            callback_query = Mock(spec=CallbackQuery)
            callback_query.data = callback_data
            callback_query.from_user = user
            callback_query.message = message
            callback_query.answer = AsyncMock()
            callback_query.edit_message_text = AsyncMock()
            update.callback_query = callback_query

        return update, message

    def _create_mock_context(self):
        """Создать mock Context"""
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = []
        context.user_data = {}
        return context

    async def test_start_command(self):
        """Тест команды /start"""
        print("\n🧪 Тестирую /start команду...")

        update, message = self._create_mock_update(text="/start")
        context = self._create_mock_context()

        try:
            await self.bot.start(update, context)

            # Проверяем что reply_text был вызван
            assert message.reply_text.called, "❌ reply_text не вызван"

            # Получаем текст ответа
            call_args = message.reply_text.call_args
            response_text = call_args[0][0] if call_args[0] else call_args[1].get('text', '')

            # Проверки
            checks = [
                ("Приветствие есть", "🏃" in response_text),
                ("Есть inline кнопки", 'reply_markup' in call_args[1]),
                ("Упоминание команд", any(cmd in response_text for cmd in ['/sync', '/stats', '/plan'])),
            ]

            for check_name, result in checks:
                status = "✅" if result else "❌"
                print(f"  {status} {check_name}")
                self.results.append((f"/start - {check_name}", result))

            # Проверяем inline кнопки
            if 'reply_markup' in call_args[1]:
                keyboard = call_args[1]['reply_markup'].inline_keyboard
                button_count = sum(len(row) for row in keyboard)
                print(f"  ✅ Найдено {button_count} inline кнопок")
                self.results.append((f"/start - Inline кнопки ({button_count})", button_count == 4))

            print("✅ /start команда работает")
            return True

        except Exception as e:
            print(f"❌ Ошибка в /start: {e}")
            self.results.append(("/start", False))
            import traceback
            traceback.print_exc()
            return False

    async def test_stats_command(self):
        """Тест команды /stats"""
        print("\n🧪 Тестирую /stats команду...")

        update, message = self._create_mock_update(text="/stats")
        context = self._create_mock_context()

        try:
            await self.bot.stats(update, context)

            assert message.reply_text.called, "❌ reply_text не вызван"

            call_args = message.reply_text.call_args
            response_text = call_args[0][0] if call_args[0] else call_args[1].get('text', '')

            # Проверки
            checks = [
                ("Есть заголовок статистики", "📊" in response_text or "Статистика" in response_text),
                ("parse_mode=Markdown", call_args[1].get('parse_mode') == 'Markdown'),
            ]

            for check_name, result in checks:
                status = "✅" if result else "❌"
                print(f"  {status} {check_name}")
                self.results.append((f"/stats - {check_name}", result))

            print("✅ /stats команда работает")
            return True

        except Exception as e:
            print(f"❌ Ошибка в /stats: {e}")
            self.results.append(("/stats", False))
            import traceback
            traceback.print_exc()
            return False

    async def test_plan_command(self):
        """Тест команды /plan"""
        print("\n🧪 Тестирую /plan команду...")

        update, message = self._create_mock_update(text="/plan")
        context = self._create_mock_context()

        try:
            await self.bot.plan(update, context)

            assert message.reply_text.called, "❌ reply_text не вызван"

            call_args = message.reply_text.call_args
            response_text = call_args[0][0] if call_args[0] else call_args[1].get('text', '')

            # Проверки
            checks = [
                ("Есть упоминание плана", "план" in response_text.lower() or "📅" in response_text),
                ("Есть кнопки выбора цели или план", 'reply_markup' in call_args[1] or "тренировок" in response_text.lower()),
            ]

            for check_name, result in checks:
                status = "✅" if result else "❌"
                print(f"  {status} {check_name}")
                self.results.append((f"/plan - {check_name}", result))

            print("✅ /plan команда работает")
            return True

        except Exception as e:
            print(f"❌ Ошибка в /plan: {e}")
            self.results.append(("/plan", False))
            import traceback
            traceback.print_exc()
            return False

    async def test_help_command(self):
        """Тест команды /help"""
        print("\n🧪 Тестирую /help команду...")

        update, message = self._create_mock_update(text="/help")
        context = self._create_mock_context()

        try:
            await self.bot.help_command(update, context)

            assert message.reply_text.called, "❌ reply_text не вызван"

            call_args = message.reply_text.call_args
            response_text = call_args[0][0] if call_args[0] else call_args[1].get('text', '')

            # Проверки
            checks = [
                ("Список команд", any(cmd in response_text for cmd in ['/start', '/sync', '/stats', '/plan'])),
                ("Описание функций", len(response_text) > 100),
            ]

            for check_name, result in checks:
                status = "✅" if result else "❌"
                print(f"  {status} {check_name}")
                self.results.append((f"/help - {check_name}", result))

            print("✅ /help команда работает")
            return True

        except Exception as e:
            print(f"❌ Ошибка в /help: {e}")
            self.results.append(("/help", False))
            import traceback
            traceback.print_exc()
            return False

    async def test_quick_actions(self):
        """Тест inline кнопок quick actions"""
        print("\n🧪 Тестирую inline кнопки quick actions...")

        actions = ['quick_stats', 'quick_plan', 'quick_sync', 'quick_calendar']

        for action in actions:
            print(f"\n  Тестирую кнопку: {action}")
            update, message = self._create_mock_update(callback_data=action)
            context = self._create_mock_context()

            try:
                await self.bot.handle_quick_actions(update, context)

                # Проверяем что callback query был обработан
                assert update.callback_query.answer.called, f"❌ callback answer не вызван для {action}"

                print(f"  ✅ {action} работает")
                self.results.append((f"Quick action - {action}", True))

            except Exception as e:
                print(f"  ❌ Ошибка в {action}: {e}")
                self.results.append((f"Quick action - {action}", False))

        return True

    def print_summary(self):
        """Вывести итоговый отчёт"""
        print("\n" + "=" * 60)
        print("📊 ИТОГОВЫЙ ОТЧЁТ ТЕСТИРОВАНИЯ UX")
        print("=" * 60)

        passed = sum(1 for _, result in self.results if result)
        total = len(self.results)

        print(f"\n✅ Пройдено: {passed}/{total}")
        print(f"❌ Провалено: {total - passed}/{total}")
        print(f"📈 Процент успеха: {(passed/total*100):.1f}%\n")

        if total - passed > 0:
            print("❌ Проваленные тесты:")
            for test_name, result in self.results:
                if not result:
                    print(f"  • {test_name}")
        else:
            print("🎉 Все тесты пройдены успешно!")

        print("\n" + "=" * 60)

    async def run_all_tests(self):
        """Запустить все тесты"""
        print("🚀 Запуск автоматизированного UX тестирования...")
        print("=" * 60)

        # Очищаем БД тестового пользователя
        try:
            user = db.get_or_create_user(self.test_user_id)
            print(f"📝 Тестовый пользователь создан: ID={user.id}")
        except Exception as e:
            print(f"⚠️  Ошибка создания тестового пользователя: {e}")

        # Запускаем тесты
        tests = [
            self.test_start_command,
            self.test_stats_command,
            self.test_plan_command,
            self.test_help_command,
            self.test_quick_actions,
        ]

        for test in tests:
            try:
                await test()
            except Exception as e:
                print(f"❌ Критическая ошибка в тесте: {e}")
                import traceback
                traceback.print_exc()

        # Итоговый отчёт
        self.print_summary()


async def main():
    """Главная функция"""
    tester = BotTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
