# 🚀 Быстрый старт

> Связано: [ТЗ](../Инфраструктура/{bot-trainer} {spec} ТЗ.md) | [Архитектура](../Инфраструктура/{bot-trainer} {spec} Архитектура.md) | [Бэклог](../Инфраструктура/{bot-trainer} {spec} Бэклог.md)

---


## Шаг 1: Создать Telegram-бота

1. Открыть Telegram, найти [@BotFather](https://t.me/BotFather)
2. Отправить команду `/newbot`
3. Ввести имя бота (например: "Мой Тренер")
4. Ввести username бота (должен заканчиваться на `bot`, например: `my_running_coach_bot`)
5. Скопировать API-токен (формат: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

## Шаг 2: Получить Claude API ключ

1. Зайти на [console.anthropic.com](https://console.anthropic.com)
2. Создать аккаунт (если нет)
3. Перейти в раздел "API Keys"
4. Создать новый ключ → скопировать (формат: `sk-ant-...`)

**Альтернатива:** OpenAI API ключ ([platform.openai.com](https://platform.openai.com/api-keys))

## Шаг 3: Настроить переменные окружения

```bash
cd bot_trainer
cp .env.example .env
nano .env
```

Заполнить:
```bash
TELEGRAM_BOT_TOKEN=<<ВСТАВЬ_ТОКЕН_ИЗ_BOTFATHER>>
GARMIN_EMAIL=<<ТВОЙ_EMAIL_GARMIN>>
GARMIN_PASSWORD=<<ТВОЙ_ПАРОЛЬ_GARMIN>>
ANTHROPIC_API_KEY=<<ВСТАВЬ_КЛЮЧ_CLAUDE>>
```

Сохранить: `Ctrl+O`, `Enter`, выйти: `Ctrl+X`

## Шаг 4: Установить зависимости

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Шаг 5: Инициализировать БД

```bash
python src/database/init_db.py
```

Должно появиться:
```
✅ База данных инициализирована
```

## Шаг 6: Запустить бота

```bash
python main.py
```

Должно появиться:
```
🚀 Бот запущен
```

## Шаг 7: Протестировать

1. Открыть Telegram
2. Найти своего бота по username (из Шага 1)
3. Нажать "Start" или отправить `/start`
4. Должно прийти приветственное сообщение

## Команды для тестирования

- `/start` — Приветствие
- `/help` — Список команд
- `/sync` — Синхронизация с Garmin (загружает тренировки за сегодня)

## Тестирование Garmin отдельно

Можно протестировать Garmin-интеграцию без запуска бота:

```bash
python test_garmin.py
```

Должно появиться:
```
✅ Сохранено N тренировок
```

Или:
```
ℹ️  Тренировок за сегодня нет
```

## Остановка бота

В терминале нажать `Ctrl+C`

---

## Проблемы?

### Ошибка "TELEGRAM_BOT_TOKEN not found"
- Проверить, что файл `.env` создан и заполнен
- Проверить, что токен скопирован полностью (без пробелов)

### Ошибка "Failed to connect to Telegram"
- Проверить интернет-соединение
- Проверить, что токен действительный (не истёк)

### Ошибка "Module not found"
- Убедиться, что виртуальное окружение активировано: `source venv/bin/activate`
- Переустановить зависимости: `pip install -r requirements.txt`

---

**Следующий этап:** Интеграция с Garmin (см. документацию)
