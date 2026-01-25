#!/bin/bash
# Тестирование бота через Telegram Desktop приложение

BOT_USERNAME="training_dag_run_bot"
SCREENSHOTS_DIR="/Users/noor/Documents/Obsidian Vault/Бот тренера/screenshots"
TELEGRAM_APP="/Applications/Telegram 2.app"

echo "======================================================================"
echo "🌐 ТЕСТИРОВАНИЕ ЧЕРЕЗ TELEGRAM DESKTOP"
echo "======================================================================"
echo "Дата: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Приложение: Telegram Desktop"
echo "Бот: @$BOT_USERNAME"
echo "======================================================================"
echo ""

# Проверка наличия Telegram
if [ ! -d "$TELEGRAM_APP" ]; then
    echo "❌ Telegram Desktop не найден по пути: $TELEGRAM_APP"
    echo "   Установи Telegram Desktop или укажи правильный путь"
    exit 1
fi

# Создаем папку для скриншотов
mkdir -p "$SCREENSHOTS_DIR"

echo "🚀 Запускаю Telegram Desktop..."
open "$TELEGRAM_APP"
sleep 3

echo "✅ Telegram Desktop запущен"
echo ""

# Открываем чат с ботом через AppleScript
echo "🔍 Открываю чат с ботом @$BOT_USERNAME..."
osascript <<EOF
tell application "Telegram"
    activate
    delay 1
end tell

-- Эмулируем Cmd+K для открытия поиска
tell application "System Events"
    tell process "Telegram"
        keystroke "k" using command down
        delay 1

        -- Вводим имя бота
        keystroke "@$BOT_USERNAME"
        delay 2

        -- Нажимаем Enter
        keystroke return
        delay 2
    end tell
end tell
EOF

echo "✅ Чат с ботом должен быть открыт"
echo ""

# Инструкции для ручного тестирования
echo "======================================================================"
echo "💡 ПЛАН ТЕСТИРОВАНИЯ"
echo "======================================================================"
echo ""

echo "ШАГ 1: Отправь команду /start"
echo "   • Должны появиться 4 inline кнопки:"
echo "     - 📊 Статистика"
echo "     - 📅 План"
echo "     - 🔄 Синхронизация"
echo "     - 📲 Календарь"
echo ""

echo "ШАГ 2: Проверь каждую inline кнопку"
echo "   • Нажми 📊 Статистика"
echo "   • Нажми 📅 План"
echo "   • Нажми 🔄 Синхронизация"
echo "   • Нажми 📲 Календарь (должен отправить ICS файл)"
echo ""

echo "ШАГ 3: Протестируй команды"
echo "   • /help - справка"
echo "   • /stats - статистика (если зарегистрирован Garmin)"
echo "   • /plan - создание плана тренировок"
echo "   • /calendar - экспорт в календарь (ICS файл)"
echo ""

echo "ШАГ 4: Проверь форматирование"
echo "   • Сообщения должны быть отформатированы (жирный текст, списки)"
echo "   • Emoji должны отображаться"
echo "   • Никаких Markdown символов как текст (нет ** или __)"
echo ""

echo "ШАГ 5: Проверь edge cases"
echo "   • Отправь /stats без регистрации Garmin - должно быть понятное сообщение"
echo "   • Отправь /plan - должен сгенерировать план"
echo "   • Проверь что календарь отправляет файл, а не ошибку"
echo ""

echo "======================================================================"
echo "📋 ЧЕКЛИСТ"
echo "======================================================================"
echo ""
echo "[ ] /start показывает приветствие + 4 кнопки"
echo "[ ] Inline кнопки работают (все 4)"
echo "[ ] /help показывает справку"
echo "[ ] /stats работает (или показывает ошибку о Garmin)"
echo "[ ] /plan генерирует план тренировок"
echo "[ ] /calendar отправляет ICS файл (не ошибку OAuth)"
echo "[ ] Форматирование Markdown работает"
echo "[ ] Emoji отображаются"
echo "[ ] Нет технических ошибок"
echo ""

echo "======================================================================"
echo "⏳ ТЕСТИРОВАНИЕ В ПРОЦЕССЕ"
echo "======================================================================"
echo ""
echo "Telegram Desktop открыт и готов к тестированию"
echo "Протестируй бота вручную по чеклисту выше"
echo ""
echo "Нажми Enter когда закончишь тестирование..."
read

echo ""
echo "======================================================================"
echo "✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО"
echo "======================================================================"
echo "Telegram Desktop остается открытым для дальнейшего использования"
echo ""
