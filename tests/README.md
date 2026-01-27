# Тестирование бота-тренера

## Структура тестов

```
tests/
├── integration/              # Integration тесты (быстрые, без Telegram)
│   ├── conftest.py          # Fixtures для моков
│   ├── test_goal_selection.py
│   ├── test_race_type_selection.py
│   └── test_days_selection.py
│
├── e2e/                     # E2E тесты (медленные, с Telethon)
│   └── [для будущих тестов с my.telegram.org]
│
└── [legacy файлы]           # Старые CDP/Selenium тесты
```

## Быстрый старт

### Integration тесты (рекомендуется для разработки)

```bash
cd "/Users/noor/Documents/Obsidian Vault/Бот тренера/bot_trainer"

# Установить pytest
pip install pytest pytest-asyncio

# Запустить все integration тесты
pytest tests/integration/ -v

# Запустить конкретный файл
pytest tests/integration/test_goal_selection.py -v
```

### Legacy E2E тесты (CDP)

```bash
cd "/Users/noor/Documents/Obsidian Vault/Бот тренера/bot_trainer/tests"

# Базовый тест (API)
python3 bot_tester.py

# Полный E2E с кликами по кнопкам
python3 cdp_bot_tester.py
```

---

## Integration тесты (новые, быстрые)

### Что это

Integration тесты проверяют handlers бота **напрямую через моки**, без запуска Telegram.

**Преимущества:**
- Очень быстрые (миллисекунды)
- Не требуют сети/токена
- Работают локально и в CI/CD
- Изолированные от внешних зависимостей

### Установка

```bash
pip install pytest pytest-asyncio
```

### Запуск

```bash
# Все integration тесты
pytest tests/integration/ -v

# Конкретный файл
pytest tests/integration/test_goal_selection.py -v

# Конкретный тест
pytest tests/integration/test_goal_selection.py::test_handle_goal_selection_race -v

# С покрытием кода
pip install pytest-cov
pytest tests/integration/ --cov=src/bot --cov-report=html
# Отчет: htmlcov/index.html
```

### Что тестируется

**Telegram handlers:**
- `test_goal_selection.py` - выбор цели (забег/фитнес) - 3 теста
- `test_race_type_selection.py` - выбор типа забега (полумарафон/марафон/трейл) - 5 тестов
- `test_days_selection.py` - выбор дней тренировок - 6 тестов

**Бизнес-логика:**
- `test_plan_generator.py` - генерация плана с периодизацией и специфичными тренировками - 5 тестов
- `test_plan_adjuster.py` - динамическая корректировка плана при пропусках - 8 тестов

**Итого: 27 тестов, ~0.9 сек**

### Пример теста

```python
@pytest.mark.asyncio
async def test_handle_goal_selection_race(bot, mock_update, mock_context):
    """Тест выбора цели: подготовка к забегу"""
    mock_update.callback_query.data = "goal_race"

    await bot.handle_goal_selection(mock_update, mock_context)

    # Проверки
    assert 'goal_type' in mock_context.user_data
    assert mock_context.user_data['goal_type'] == 'race'
```

---

## Рабочие тестеры (Legacy CDP)

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
