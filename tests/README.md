# Тестирование бота-тренера

## Быстрый старт

```bash
cd "/Users/noor/Documents/Obsidian Vault/Бот тренера/bot_trainer/tests"

# Базовый тест (API)
python3 bot_tester.py

# Полный E2E с кликами по кнопкам
python3 cdp_bot_tester.py
```

---

## Рабочие тестеры

### 1. bot_tester.py — API тест (работает сразу)

```bash
python3 bot_tester.py
```

**Что проверяет:**
- Бот онлайн
- Команды зарегистрированы
- Режим работы (polling/webhook)

---

### 2. cdp_bot_tester.py — E2E с кликами (рекомендуется)

```bash
python3 cdp_bot_tester.py
```

**Что делает:**
- Запускает Chrome с CDP (Chrome DevTools Protocol)
- Открывает Telegram Web
- Отправляет /start
- **Кликает по inline кнопкам** (настоящие клики через CDP)
- Проверяет ответы бота

**Требования:**
- Chrome установлен
- Авторизация в Telegram (делается один раз)

**Почему работает:**
CDP события являются "trusted" и обходят browser security, в отличие от Selenium JavaScript clicks.

---

## Первый запуск cdp_bot_tester.py

1. Запусти тест:
   ```bash
   python3 cdp_bot_tester.py
   ```

2. Откроется Chrome. Если не авторизован в Telegram:
   - Войди по QR-коду или телефону
   - Тест подождёт 30 секунд

3. Сессия сохранится в профиле `~/Library/Application Support/Google/Chrome/BotTesting`

4. При следующих запусках авторизация не нужна

---

## Пример вывода

```
✅ Chrome уже запущен
✅ Подключён к Chrome через CDP
✅ Авторизован в Telegram
✅ Страница бота открыта
✅ Команда /start отправлена
✅ Найдено 4 кнопок в последнем сообщении
   ✓ 📊 Статистика
   ✓ 📅 План
   ✓ 🔄 Синхронизация
   ✓ 📲 Календарь

🖱️  Кликаю: 📊 Статистика
✅    Клик выполнен
✅    Бот ответил

🎉 CDP ТЕСТИРОВАНИЕ УСПЕШНО!
```

---

## Файлы

| Файл | Назначение | Статус |
|------|-----------|--------|
| `cdp_bot_tester.py` | **E2E с кликами через CDP** | ✅ Работает |
| `bot_tester.py` | API проверка | ✅ Работает |
| `final_check.py` | Быстрая API проверка | ✅ Работает |

---

## Устаревшие файлы

Можно удалить — это неудачные попытки через Selenium:

```bash
rm chrome_*.py selenium_*.py browser_*.py *_simulation.py
```

---

## Troubleshooting

### Chrome не запускается
```bash
# Убить старые процессы
pkill -f "Chrome.*9222"

# Перезапустить тест
python3 cdp_bot_tester.py
```

### Кнопки не находятся
- Убедись что бот ответил на /start
- Проверь скриншот в `/tmp/telegram_test.png`

### Ошибка подключения к CDP
```bash
# Проверь порт
curl http://localhost:9222/json/version
```

---

*Обновлено: 2026-01-25*
