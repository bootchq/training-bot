#!/usr/bin/env python3
"""
Unit тесты для бота - РЕАЛЬНОЕ тестирование логики
Симулирую Update объекты и вызываю handlers напрямую
"""

import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

# Добавляем путь к модулям бота
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from bot.telegram_bot import TelegramTrainingBot


class TestBotLogic:
    """Тесты логики бота"""

    def setup_method(self):
        """Подготовка к каждому тесту"""
        self.bot = TelegramTrainingBot()

    async def create_mock_update(self, text="/start", user_id=12345):
        """Создать mock Update объект"""
        update = Mock()
        update.effective_user = Mock()
        update.effective_user.id = user_id
        update.effective_user.first_name = "Test User"

        update.message = Mock()
        update.message.text = text
        update.message.reply_text = AsyncMock()
        update.message.reply_document = AsyncMock()
        update.message.chat = Mock()
        update.message.chat.id = user_id

        update.callback_query = None

        return update

    async def create_mock_context(self):
        """Создать mock Context объект"""
        context = Mock()
        context.user_data = {}
        context.bot = Mock()
        context.bot.send_message = AsyncMock()

        return context

    async def test_start_command(self):
        """Тест команды /start"""
        print("\n🧪 ТЕСТ 1: Команда /start")
        print("-" * 70)

        update = await self.create_mock_update("/start")
        context = await self.create_mock_context()

        # Вызываем handler
        await self.bot.start(update, context)

        # Проверяем что reply_text был вызван
        assert update.message.reply_text.called, "reply_text не был вызван"

        # Получаем аргументы вызова
        call_args = update.message.reply_text.call_args

        if call_args:
            # Проверяем текст
            text = call_args[0][0] if call_args[0] else call_args[1].get('text', '')
            print(f"✅ Ответ бота:\n{text[:200]}...")

            # Проверяем inline кнопки
            if 'reply_markup' in call_args[1]:
                markup = call_args[1]['reply_markup']
                if hasattr(markup, 'inline_keyboard'):
                    buttons = markup.inline_keyboard
                    print(f"✅ Найдено {len(buttons)} рядов inline кнопок")

                    for row in buttons:
                        for btn in row:
                            print(f"   🔘 {btn.text} → {btn.callback_data}")

                    # Проверяем что есть 4 ожидаемые кнопки
                    all_buttons = [btn for row in buttons for btn in row]
                    expected_texts = ["📊 Статистика", "📅 План", "🔄 Синхронизация", "📲 Календарь"]

                    for expected in expected_texts:
                        found = any(expected in btn.text for btn in all_buttons)
                        if found:
                            print(f"   ✅ Кнопка '{expected}' найдена")
                        else:
                            print(f"   ❌ Кнопка '{expected}' НЕ найдена")

                    return len(all_buttons) >= 4
        else:
            print("⚠️  Аргументы вызова не найдены")

        return False

    async def test_help_command(self):
        """Тест команды /help"""
        print("\n🧪 ТЕСТ 2: Команда /help")
        print("-" * 70)

        update = await self.create_mock_update("/help")
        context = await self.create_mock_context()

        await self.bot.help_command(update, context)

        assert update.message.reply_text.called, "/help не ответил"

        call_args = update.message.reply_text.call_args
        if call_args:
            text = call_args[0][0] if call_args[0] else call_args[1].get('text', '')
            print(f"✅ Справка получена:\n{text[:200]}...")
            return True

        return False

    async def test_calendar_command(self):
        """Тест команды /calendar - КРИТИЧЕСКИЙ ТЕСТ"""
        print("\n🧪 ТЕСТ 3: Команда /calendar (ICS файл, не OAuth!)")
        print("-" * 70)

        update = await self.create_mock_update("/calendar")
        context = await self.create_mock_context()

        # Mock database
        with patch('bot.telegram_bot.db') as mock_db:
            mock_user = Mock()
            mock_user.id = 1
            mock_db.get_or_create_user.return_value = mock_user
            mock_db.get_plan_for_week.return_value = []  # Нет плана

            await self.bot.calendar(update, context)

            # Проверяем что НЕ было попытки OAuth
            call_args = update.message.reply_text.call_args
            if call_args:
                text = call_args[0][0] if call_args[0] else call_args[1].get('text', '')

                if 'OAuth' in text or 'авторизоваться' in text:
                    print("❌ FAIL: Бот пытается использовать OAuth!")
                    print(f"   Текст: {text}")
                    return False

                # Должно быть сообщение о создании плана
                if 'план' in text.lower() or 'создай' in text.lower():
                    print("✅ PASS: Бот просит создать план (правильно)")
                    print(f"   Текст: {text[:200]}...")
                    return True

        print("⚠️  Неопределенный результат")
        return False


async def run_all_tests():
    """Запуск всех тестов"""
    print("="*70)
    print("🤖 UNIT ТЕСТЫ БОТА - АВТОМАТИЧЕСКОЕ ТЕСТИРОВАНИЕ ЛОГИКИ")
    print("="*70)
    print(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

    tester = TestBotLogic()
    tester.setup_method()

    results = []

    # Тест 1: /start
    try:
        result1 = await tester.test_start_command()
        results.append(("Команда /start", result1))
    except Exception as e:
        print(f"❌ Ошибка в тесте /start: {e}")
        results.append(("Команда /start", False))

    # Тест 2: /help
    try:
        result2 = await tester.test_help_command()
        results.append(("Команда /help", result2))
    except Exception as e:
        print(f"❌ Ошибка в тесте /help: {e}")
        results.append(("Команда /help", False))

    # Тест 3: /calendar
    try:
        result3 = await tester.test_calendar_command()
        results.append(("Команда /calendar (без OAuth)", result3))
    except Exception as e:
        print(f"❌ Ошибка в тесте /calendar: {e}")
        results.append(("Команда /calendar (без OAuth)", False))

    # Итоги
    print("\n" + "="*70)
    print("📊 РЕЗУЛЬТАТЫ UNIT ТЕСТОВ")
    print("="*70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} | {name}")

    print("="*70)
    percent = (passed * 100 // total) if total > 0 else 0
    print(f"Результат: {passed}/{total} тестов пройдено ({percent}%)")
    print("="*70)

    if percent == 100:
        print("🎉 ВСЕ UNIT ТЕСТЫ ПРОШЛИ!")
    elif percent >= 80:
        print("✅ Большинство тестов пройдено")
    else:
        print("⚠️  Требуется доработка")


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_all_tests())
