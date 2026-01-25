#!/bin/bash
# Запускает Chrome с remote debugging и сохранением сессии
# ОДИН РАЗ авторизуйся - дальше сессия сохранена!

CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE_DIR="$HOME/Library/Application Support/Google/Chrome/BotTesting"

echo "======================================================================"
echo "🚀 ЗАПУСК CHROME ДЛЯ ТЕСТИРОВАНИЯ БОТА"
echo "======================================================================"
echo ""
echo "Этот Chrome:"
echo "   ✅ Сохраняет сессию Telegram"
echo "   ✅ Работает с remote debugging"
echo "   ✅ НЕ НУЖНО авторизовываться каждый раз!"
echo ""
echo "======================================================================"
echo ""

# Создаем папку профиля
mkdir -p "$PROFILE_DIR"

echo "📂 Профиль: $PROFILE_DIR"
echo "🌐 Открываю Chrome..."
echo ""

# Запускаем Chrome
"$CHROME_PATH" \
  --remote-debugging-port=9222 \
  --user-data-dir="$PROFILE_DIR" \
  --no-first-run \
  --no-default-browser-check \
  "https://web.telegram.org/k/" &

CHROME_PID=$!

echo "✅ Chrome запущен (PID: $CHROME_PID)"
echo ""
echo "======================================================================"
echo "💡 ЧТО ДЕЛАТЬ ДАЛЬШЕ"
echo "======================================================================"
echo ""
echo "ПЕРВЫЙ ЗАПУСК:"
echo "   1. Авторизуйся в Telegram через QR-код"
echo "   2. Сессия сохранится автоматически"
echo ""
echo "ТЕСТИРОВАНИЕ:"
echo "   Запусти в другом терминале:"
echo "   python3 tests/connect_to_chrome.py"
echo ""
echo "   Скрипт подключится к этому Chrome и:"
echo "   ✅ Найдет бота"
echo "   ✅ Отправит /start"
echo "   ✅ КЛИКНЕТ ПО ВСЕМ КНОПКАМ"
echo "   ✅ Сделает скриншоты"
echo ""
echo "======================================================================"
echo ""
echo "Chrome работает в фоне (PID: $CHROME_PID)"
echo "Чтобы остановить: kill $CHROME_PID"
echo ""
