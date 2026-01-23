# Railway Setup - Финальные шаги

**Проект:** https://railway.com/project/acf22966-f165-4e4d-a9ba-ce2efef63129

✅ Код загружен на Railway
✅ Сервис создан автоматически

---

## Шаг 1: Подключить GitHub репозиторий

1. Открой проект: https://railway.com/project/acf22966-f165-4e4d-a9ba-ce2efef63129
2. Найди созданный сервис (должен быть один с кодом)
3. Нажми на сервис → **Settings**
4. В разделе **Source** нажми **Connect Repo**
5. Выбери репозиторий **bootchq/training-bot**
6. Сохрани

Это включит автоматический деплой при push в GitHub.

---

## Шаг 2: Настроить переменные окружения

В Railway проекте → выбери сервис → вкладка **Variables** → добавь:

```bash
# Telegram Bot
TELEGRAM_BOT_TOKEN=8219028377:AAHDhNNoVGfPWA4XJL1PNjD4ZcDJJkuWxyI

# Garmin Connect
GARMIN_EMAIL=bootchq@gmail.com
GARMIN_PASSWORD=Aa1424617556

# Groq AI (бесплатный - получить на https://console.groq.com)
GROQ_API_KEY=<<ПОЛУЧИ_НА_GROQ_CONSOLE>>

# Database
DATABASE_PATH=/data/training_bot.db

# Timezone
TZ=Europe/Moscow

# Logging
LOG_LEVEL=INFO
```

**Важно:** Получи Groq API ключ (бесплатно):
- Инструкция: [docs/groq_api_setup.md](groq_api_setup.md)
- URL: https://console.groq.com
- Войди через Google (bootchq@gmail.com)
- Создай API Key → скопируй ключ (начинается с `gsk_...`)

После добавления Railway автоматически перезапустит сервис.

---

## Шаг 3: Добавить Volume для базы данных

1. В проекте нажми **+ New** → **Volume**
2. Настройки:
   - **Name:** training-data
   - **Mount Path:** /data
3. Подключи Volume к сервису (нажми на Volume → **Connect to Service**)
4. Выбери свой сервис

---

## Шаг 4: Настроить домен для health check

1. Сервис → **Settings** → **Networking**
2. Нажми **Generate Domain**
3. Скопируй сгенерированный URL (например: `training-bot-production.up.railway.app`)

Этот URL понадобится для UptimeRobot.

---

## Шаг 5: Проверить деплой

### Проверка логов

1. Сервис → вкладка **Deployments**
2. Нажми на последний деплой
3. Смотри логи - должно быть:
   ```
   🏃 Запуск бота-тренера
   ✅ База данных инициализирована
   ✅ Health check сервер запущен на порту XXXX
   ✅ Бот запущен: @your_bot_username
   ```

### Проверка health endpoint

Открой в браузере:
```
https://[твой-домен].railway.app/health
```

Должен вернуть JSON:
```json
{
  "status": "healthy",
  "service": "training-bot",
  "uptime_seconds": 123
}
```

### Проверка бота

1. Открой Telegram
2. Найди своего бота
3. Отправь `/start`
4. Проверь команды: `/help`, `/stats`, `/plan`

---

## Шаг 6: Google Calendar токены

Google OAuth требует файлы `credentials.json` и `token.json`.

### Вариант A: Локальная авторизация + загрузка через Railway CLI

```bash
# 1. Авторизоваться локально
cd bot_trainer
source venv/bin/activate
python -c "from src.integrations.calendar_sync import calendar_sync; calendar_sync.authenticate()"

# 2. Загрузить на Railway
cd bot_trainer
cat config/credentials.json | railway variables set --stdin GOOGLE_CREDENTIALS_JSON
cat config/token.json | railway variables set --stdin GOOGLE_TOKEN_JSON
```

### Вариант B: Через Volume (если Railway CLI не работает)

1. Сначала авторизуйся локально (команда выше)
2. Используй Railway web shell:
   - Сервис → **Settings** → **Deploy**
   - Включи **Railway Shell**
   - В shell выполни:
     ```bash
     mkdir -p /data
     cat > /data/credentials.json << 'EOF'
     [содержимое config/credentials.json]
     EOF

     cat > /data/token.json << 'EOF'
     [содержимое config/token.json]
     EOF
     ```

Или просто скопируй файлы вручную через web shell.

---

## Следующий шаг: UptimeRobot

После того как бот работает на Railway:

1. Зайди на https://uptimerobot.com
2. Создай новый монитор:
   - **Type:** HTTP(s)
   - **URL:** `https://[твой-домен].railway.app/health`
   - **Interval:** 5 minutes
3. Сохрани

Теперь Railway не будет засыпать.

---

## Troubleshooting

### Деплой падает с ошибкой
- Проверь логи в **Deployments**
- Убедись что все переменные окружения установлены
- Проверь что Volume подключён

### Бот не отвечает
- Проверь `TELEGRAM_BOT_TOKEN` в переменных
- Убедись что бот не запущен локально
- Проверь логи Railway

### Google Calendar не работает
- Убедись что `credentials.json` и `token.json` загружены
- Проверь логи на наличие OAuth ошибок

---

**Статус:** 🚀 Код на Railway, осталось настроить переменные и Volume
