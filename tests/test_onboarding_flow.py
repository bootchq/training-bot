#!/usr/bin/env python3
"""
Unit-тест для онбординга
Проверяет логику без реального Telegram API
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock

# Мокаем telegram модули
sys.modules['telegram'] = MagicMock()
sys.modules['telegram.ext'] = MagicMock()

def test_onboarding_handlers_exist():
    """Проверка что все обработчики онбординга определены"""
    from src.bot.telegram_bot import TrainingBot

    bot = TrainingBot()

    # Проверяем что методы существуют
    assert hasattr(bot, 'handle_start_onboarding'), "handle_start_onboarding не найден"
    assert hasattr(bot, 'handle_goal_selection'), "handle_goal_selection не найден"
    assert hasattr(bot, 'handle_race_type_selection'), "handle_race_type_selection не найден"
    assert hasattr(bot, 'handle_days_selection'), "handle_days_selection не найден"
    assert hasattr(bot, '_show_days_selection'), "_show_days_selection не найден"

    print("✅ Все обработчики онбординга существуют")
    return True


def test_callback_patterns():
    """Проверка что callback patterns корректны"""

    # Ожидаемые patterns
    expected_patterns = [
        "^start_onboarding$",
        "^goal_",
        "^racetype_",
        "^trainday_",
    ]

    # Читаем файл бота
    bot_file = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            'src', 'bot', 'telegram_bot.py')

    with open(bot_file) as f:
        content = f.read()

    for pattern in expected_patterns:
        assert pattern in content, f"Pattern {pattern} не найден в telegram_bot.py"
        print(f"✅ Pattern найден: {pattern}")

    print("✅ Все callback patterns корректны")
    return True


def test_goal_callbacks():
    """Проверка callback_data для целей"""

    bot_file = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            'src', 'bot', 'telegram_bot.py')

    with open(bot_file) as f:
        content = f.read()

    # Проверяем callback_data для целей
    goal_callbacks = [
        'callback_data="goal_race"',
        'callback_data="goal_fitness"',
    ]

    for cb in goal_callbacks:
        assert cb in content, f"Callback {cb} не найден"
        print(f"✅ Callback найден: {cb}")

    # Проверяем callback_data для типов забега
    race_callbacks = [
        'callback_data="racetype_half"',
        'callback_data="racetype_marathon"',
        'callback_data="racetype_custom"',
        'callback_data="racetype_trail"',
    ]

    for cb in race_callbacks:
        assert cb in content, f"Callback {cb} не найден"
        print(f"✅ Callback найден: {cb}")

    # Проверяем callback_data для дней
    for day in range(1, 8):
        cb = f'callback_data="trainday_{day}"'
        assert cb in content, f"Callback {cb} не найден"
        print(f"✅ Callback найден: {cb}")

    assert 'callback_data="trainday_done"' in content, "trainday_done не найден"
    print("✅ Callback trainday_done найден")

    print("✅ Все callback_data корректны")
    return True


def test_onboarding_flow_structure():
    """Проверка структуры flow онбординга"""

    bot_file = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            'src', 'bot', 'telegram_bot.py')

    with open(bot_file) as f:
        content = f.read()

    # Проверяем что handle_start_onboarding показывает выбор race/fitness
    assert 'Подготовка к забегу' in content, "Текст 'Подготовка к забегу' не найден"
    assert 'Тренировки для себя' in content, "Текст 'Тренировки для себя' не найден"
    print("✅ handle_start_onboarding показывает правильные кнопки")

    # Проверяем что handle_goal_selection показывает типы забега для race
    assert 'Полумарафон' in content, "Текст 'Полумарафон' не найден"
    assert 'Марафон' in content, "Текст 'Марафон' не найден"
    assert 'Своя дистанция' in content, "Текст 'Своя дистанция' не найден"
    assert 'Трейл' in content, "Текст 'Трейл' не найден"
    print("✅ handle_goal_selection показывает типы забега")

    # Проверяем что есть обработка трейла
    assert 'awaiting_trail_distance' in content, "awaiting_trail_distance не найден"
    print("✅ Обработка трейла настроена")

    # Проверяем что _show_days_selection вызывается
    assert '_show_days_selection' in content, "_show_days_selection не найден"
    print("✅ _show_days_selection определён и используется")

    print("✅ Структура flow онбординга корректна")
    return True


def test_handler_registration():
    """Проверка что handlers зарегистрированы в правильном порядке"""

    bot_file = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            'src', 'bot', 'telegram_bot.py')

    with open(bot_file) as f:
        content = f.read()

    # Находим позиции registration
    handlers = [
        'handle_start_onboarding',
        'handle_goal_selection',
        'handle_race_type_selection',
        'handle_days_selection',
    ]

    positions = {}
    for h in handlers:
        pos = content.find(f'add_handler(CallbackQueryHandler(self.{h}')
        assert pos > 0, f"Handler {h} не зарегистрирован"
        positions[h] = pos

    # Проверяем порядок
    sorted_handlers = sorted(positions.keys(), key=lambda x: positions[x])
    print(f"✅ Порядок регистрации handlers: {sorted_handlers}")

    # Проверяем что все handlers до ConversationHandlers (регистрация)
    conv_handler_pos = content.find('self.app.add_handler(garmin_registration_handler)')
    for h, pos in positions.items():
        assert pos < conv_handler_pos, f"Handler {h} должен быть до ConversationHandlers"

    print("✅ Все handlers зарегистрированы до ConversationHandlers")
    return True


def run_all_tests():
    """Запуск всех тестов"""
    print("="*60)
    print("🧪 ТЕСТИРОВАНИЕ ОНБОРДИНГА")
    print("="*60)
    print()

    tests = [
        ("Проверка обработчиков", test_onboarding_handlers_exist),
        ("Проверка callback patterns", test_callback_patterns),
        ("Проверка callback_data", test_goal_callbacks),
        ("Проверка структуры flow", test_onboarding_flow_structure),
        ("Проверка регистрации handlers", test_handler_registration),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"🔍 {name}")
        print(f"{'='*60}")
        try:
            test_func()
            passed += 1
            print(f"\n✅ {name}: PASSED")
        except AssertionError as e:
            failed += 1
            print(f"\n❌ {name}: FAILED - {e}")
        except Exception as e:
            failed += 1
            print(f"\n❌ {name}: ERROR - {e}")

    print()
    print("="*60)
    print(f"📊 РЕЗУЛЬТАТЫ: {passed}/{passed+failed} тестов пройдено")
    print("="*60)

    if failed == 0:
        print("✅ ВСЕ ТЕСТЫ ПРОШЛИ!")
        return True
    else:
        print(f"❌ {failed} тестов провалено")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
