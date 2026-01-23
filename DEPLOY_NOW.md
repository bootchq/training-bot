# 🚀 Финальный деплой — что сделать СЕЙЧАС

**Время:** ~10 минут
**Статус:** 98% готов, осталось 3 шага

---

## ✅ Что уже сделано

- GitHub репозиторий создан: https://github.com/bootchq/training-bot
- Railway проект создан: https://railway.com/project/acf22966-f165-4e4d-a9ba-ce2efef63129
- Код загружен на Railway
- Telegram Bot создан: @training_bot (токен готов)
- Groq API интегрирован (бесплатный AI)

---

## 📋 Что сделать (3 шага)

### Шаг 1: Получить Groq API ключ (2 минуты)

1. Открой: https://console.groq.com
2. Войди через Google (bootchq@gmail.com)
3. API Keys → Create API Key → `training-bot`
4. Скопируй ключ (начинается с `gsk_...`)

**Детали:** [docs/groq_api_setup.md](docs/groq_api_setup.md)

---

### Шаг 2: Настроить Railway переменные (3 минуты)

1. Открой: https://railway.com/project/acf22966-f165-4e4d-a9ba-ce2efef63129
2. Выбери сервис (должен быть один)
3. Вкладка **Variables** → **+ New Variable**
4. Добавь эти переменные (скопируй целиком):

```bash
TELEGRAM_BOT_TOKEN=8219028377:AAHDhNNoVGfPWA4XJL1PNjD4ZcDJJkuWxyI
GARMIN_EMAIL=bootchq@gmail.com
GARMIN_PASSWORD=Aa1424617556
GROQ_API_KEY=<<ВСТАВЬ_КЛЮЧ_ИЗ_ШАГА_1>>
DATABASE_PATH=/data/training_bot.db
TZ=Europe/Moscow
LOG_LEVEL=INFO
```

5. Railway автоматически перезапустит бота

---

### Шаг 3: Добавить Volume для БД (1 минута)

1. В том же Railway проекте нажми **+ New**
2. Выбери **Volume**
3. Настройки:
   - **Name:** training-data
   - **Mount Path:** /data
4. Нажми **Connect to Service** → выбери свой сервис
5. Готово!

---

## 🎯 Проверка работы (5 минут)

### 1. Проверь логи Railway

Railway → Deployments → последний деплой → Logs

Должно быть:
```
🏃 Запуск бота-тренера
✅ База данных инициализирована
✅ Health check сервер запущен
✅ Бот запущен: @training_bot
```

### 2. Проверь бота в Telegram

1. Telegram → найди @training_bot
2. Отправь `/start`
3. Отправь `/help` — должен прийти список команд

### 3. Проверь Garmin синхронизацию

Отправь `/sync` — бот должен синхронизировать тренировки.

---

## ⚡ Опционально (позже)

### Google Calendar (для синхронизации плана)

**Когда:** После того как бот работает

1. Настроить OAuth (инструкция: [docs/google_calendar_setup.md](docs/google_calendar_setup.md))
2. Загрузить токены на Railway

### UptimeRobot (чтобы Railway не засыпал)

**Когда:** Бот работает стабильно

1. Railway → Settings → Networking → Generate Domain
2. Зарегистрироваться на https://uptimerobot.com
3. Создать монитор для `/health` endpoint
4. Интервал: 5 минут

---

## 📊 Текущий статус

| Задача | Статус |
|--------|--------|
| GitHub репозиторий | ✅ |
| Railway проект | ✅ |
| Код загружен | ✅ |
| Telegram Bot токен | ✅ |
| Groq API ключ | ⏳ Нужно получить |
| Railway переменные | ⏳ Нужно настроить |
| Railway Volume | ⏳ Нужно создать |
| Google Calendar | ⏸️ Опционально |
| UptimeRobot | ⏸️ Опционально |

---

## 🆘 Если что-то не работает

**Бот не отвечает:**
- Проверь переменные в Railway
- Проверь логи на наличие ошибок
- Убедись что токен правильный

**Garmin не синхронизируется:**
- Проверь email и пароль в переменных
- Может потребоваться капча при первом входе

**AI советы не приходят:**
- Проверь `GROQ_API_KEY` в Railway
- Посмотри логи на наличие ошибок Groq API
- Убедись что библиотека `openai` установлена (должна быть в requirements.txt)

---

**Дедлайн MVP:** 01.02.2026 (до Tarki-Tau 50km)
**Осталось:** 9 дней
