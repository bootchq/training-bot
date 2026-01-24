# 🚀 Настройка Railway (2 минуты)

## Все данные готовы — просто скопируй

### 1. Открой Railway (кликни):
https://railway.com/project/acf22966-f165-4e4d-a9ba-ce2efef63129

### 2. Выбери сервис (видишь один загруженный) → Variables

### 3. Скопируй и вставь построчно:

```
TELEGRAM_BOT_TOKEN
8219028377:AAHDhNNoVGfPWA4XJL1PNjD4ZcDJJkuWxyI
```

```
GARMIN_EMAIL
bootchq@gmail.com
```

```
GARMIN_PASSWORD
Aa1424617556
```

```
GROQ_API_KEY
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
```

```
DATABASE_PATH
/data/training_bot.db
```

```
TZ
Europe/Moscow
```

```
LOG_LEVEL
INFO
```

### 4. Создай Volume:

**+ New** → **Volume**
- Name: `training-data`
- Mount Path: `/data`
- Connect to Service → (выбери свой сервис)

**ГОТОВО!** Бот запустится автоматически.

---

## Проверка:

Telegram → @training_bot → `/start`

Если не работает — посмотри логи в Railway → Deployments → Logs
