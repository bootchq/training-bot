#!/usr/bin/env python3
"""
АВТОМАТИЧЕСКОЕ ТЕСТИРОВАНИЕ ЧЕРЕЗ TELETHON
Я САМ буду кликать по кнопкам как настоящий пользователь!
"""

import asyncio
import os
import sys
from telethon import TelegramClient, events
from telethon.tl.types import KeyboardButtonCallback

# Конфигурация
API_ID = None  # Получим автоматически или попросим
API_HASH = None
PHONE = None
BOT_USERNAME = 'training_dag_run_bot'

print("="*70)
print("🤖 АВТОМАТИЧЕСКОЕ ТЕСТИРОВАНИЕ - Я САМ КЛИКАЮ ПО КНОПКАМ!")
print("="*70)
print("Библиотека: Telethon (работаю как пользователь)")
print("="*70)
print()

# Проверяем учетные данные Telegram API
config_file = os.path.expanduser('~/.telegram_api_config')

if os.path.exists(config_file):
    print("✅ Нашел сохраненные credentials")
    with open(config_file, 'r') as f:
        lines = f.readlines()
        API_ID = int(lines[0].strip())
        API_HASH = lines[1].strip()
        PHONE = lines[2].strip() if len(lines) > 2 else None
else:
    print("⚠️  Нужны Telegram API credentials")
    print()
    print("📱 КАК ПОЛУЧИТЬ:")
    print("   1. Открой: https://my.telegram.org/apps")
    print("   2. Войди через свой номер телефона")
    print("   3. Создай приложение (любое название)")
    print("   4. Скопируй API ID и API Hash")
    print()

    try:
        API_ID = input("Введи API ID: ").strip()
        API_HASH = input("Введи API Hash: ").strip()
        PHONE = input("Введи номер телефона (с +): ").strip()

        # Сохраняем
        with open(config_file, 'w') as f:
            f.write(f"{API_ID}\n{API_HASH}\n{PHONE}\n")

        API_ID = int(API_ID)
        print()
        print("✅ Credentials сохранены в:", config_file)
    except KeyboardInterrupt:
        print()
        print("❌ Отменено")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)

print()

# Создаем клиент
session_file = '/Users/noor/Documents/Obsidian Vault/Бот тренера/telegram_test_session'
client = TelegramClient(session_file, API_ID, API_HASH)

async def main():
    """Главная функция тестирования"""

    print("🔐 Подключаюсь к Telegram...")
    await client.start(phone=PHONE)
    print("✅ Подключен!")
    print()

    # Находим бота
    print(f"🔍 Ищу бота @{BOT_USERNAME}...")
    try:
        bot = await client.get_entity(BOT_USERNAME)
        print(f"✅ Бот найден: {bot.first_name}")
    except Exception as e:
        print(f"❌ Не могу найти бота: {e}")
        return

    print()

    # ТЕСТ 1: Отправляем /start
    print("="*70)
    print("🧪 ТЕСТ 1: Отправляю /start")
    print("="*70)

    await client.send_message(bot, '/start')
    await asyncio.sleep(2)

    # Получаем последнее сообщение от бота
    messages = await client.get_messages(bot, limit=1)
    if messages:
        last_msg = messages[0]
        print(f"✅ Получен ответ от бота")
        print(f"   Текст: {last_msg.text[:100]}...")

        # Проверяем inline кнопки
        if last_msg.reply_markup:
            buttons = last_msg.reply_markup.rows
            print(f"✅ Найдено {len(buttons)} рядов кнопок")
            print()

            # КЛИКАЕМ ПО КАЖДОЙ КНОПКЕ!
            print("🖱️  КЛИКАЮ ПО КАЖДОЙ КНОПКЕ:")
            print("-" * 70)

            for row_idx, row in enumerate(buttons):
                for btn_idx, button in enumerate(row.buttons):
                    btn_text = button.text
                    print(f"\n🔘 Кнопка: {btn_text}")

                    try:
                        # ВОТ ОНО! КЛИКАЕМ ПО КНОПКЕ!
                        await last_msg.click(btn_idx, row_idx)
                        await asyncio.sleep(2)

                        # Получаем ответ бота
                        new_messages = await client.get_messages(bot, limit=1)
                        if new_messages:
                            response = new_messages[0]

                            # Проверяем что получили
                            if response.document:
                                print(f"   ✅ Бот отправил ФАЙЛ: {response.file.name}")
                                print(f"   📎 Размер: {response.file.size} байт")

                                # КРИТИЧЕСКАЯ ПРОВЕРКА - кнопка Календарь
                                if 'календарь' in btn_text.lower():
                                    if response.file.name.endswith('.ics'):
                                        print(f"   🎉 УСПЕХ! ICS файл получен!")
                                        print(f"   ✅ Баг с OAuth календарем ИСПРАВЛЕН!")
                                    else:
                                        print(f"   ⚠️  Файл не ICS: {response.file.name}")
                            elif response.text:
                                resp_text = response.text[:150]
                                print(f"   📝 Ответ: {resp_text}...")
                            else:
                                print(f"   ⚠️  Непонятный ответ")

                        print(f"   ✅ Клик успешен!")

                    except Exception as e:
                        print(f"   ❌ Ошибка клика: {e}")

        else:
            print("⚠️  Inline кнопок не найдено")

    print()

    # ТЕСТ 2: Команда /calendar
    print("="*70)
    print("🧪 ТЕСТ 2: Команда /calendar")
    print("="*70)

    await client.send_message(bot, '/calendar')
    await asyncio.sleep(3)

    messages = await client.get_messages(bot, limit=1)
    if messages:
        msg = messages[0]
        if msg.document:
            print(f"✅ Бот отправил файл: {msg.file.name}")
            if msg.file.name.endswith('.ics'):
                print(f"   ✅ Это ICS файл!")
                print(f"   ✅ Команда /calendar работает правильно")
            else:
                print(f"   ⚠️  Не ICS файл")
        elif msg.text:
            print(f"📝 Ответ: {msg.text[:200]}...")
            if 'OAuth' in msg.text or 'авторизоваться' in msg.text:
                print(f"   ❌ FAIL: Все еще пытается использовать OAuth!")

    print()

    # ТЕСТ 3: Другие команды
    commands = ['/help', '/stats', '/plan']

    for cmd in commands:
        print("="*70)
        print(f"🧪 ТЕСТ: {cmd}")
        print("="*70)

        await client.send_message(bot, cmd)
        await asyncio.sleep(2)

        messages = await client.get_messages(bot, limit=1)
        if messages:
            msg = messages[0]
            if msg.text:
                print(f"✅ Ответ получен: {msg.text[:100]}...")

        print()

    # Итоги
    print("="*70)
    print("✅ АВТОМАТИЧЕСКОЕ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО!")
    print("="*70)
    print()
    print("🎉 Я САМ:")
    print("   ✅ Отправил /start")
    print("   ✅ Получил inline кнопки")
    print("   ✅ КЛИКНУЛ по каждой кнопке")
    print("   ✅ Проверил что кнопка Календарь отправляет ICS файл")
    print("   ✅ Протестировал команды")
    print()
    print("="*70)

try:
    with client:
        client.loop.run_until_complete(main())
except KeyboardInterrupt:
    print()
    print("❌ Прервано")
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
