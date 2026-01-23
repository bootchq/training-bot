# 📋 Следующие шаги для деплоя

**Статус:** Фаза 7 — подготовка завершена (95% MVP done)

---

## ✅ Что уже сделано

1. **Инфраструктура**
   - База данных SQLite настроена
   - Логирование настроено
   - Конфигурация через .env

2. **Garmin интеграция**
   - Синхронизация тренировок работает
   - Автоматическая синхронизация в 00:00 MSK

3. **Управление планом**
   - План распарсен и загружен в БД
   - Адаптация при пропусках (best practices)
   - Адаптация по самочувствию
   - Адаптация при перевыполнении

4. **Telegram-интерфейс**
   - Все команды реализованы: `/start`, `/help`, `/stats`, `/plan`, `/sync`, `/calendar`
   - Вечерний опрос из 4 вопросов
   - Inline-кнопки для ответов

5. **Google Calendar**
   - Синхронизация с Google Calendar
   - Генерация ICS файлов для iPhone
   - OAuth авторизация

6. **AI-консультант**
   - Интеграция с Claude API
   - Советы после каждого опроса
   - Лимит 10 запросов/день
   - Fallback на шаблонные советы

7. **Подготовка к деплою**
   - `.gitignore` настроен ✅
   - `Procfile` для Railway создан ✅
   - `runtime.txt` создан ✅
   - Health check endpoint `/health` реализован ✅
   - Документация обновлена ✅
   - Инструкция по деплою готова ✅

---

## 🚀 Что нужно сделать (вручную)

### 1. Создать GitHub репозиторий

```bash
cd "/Users/noor/Documents/Obsidian Vault/Cursor/Моя жизнь/Спорт/Бот тренера/bot_trainer"

# Инициализировать git (если ещё не сделано)
git init

# Добавить все файлы
git add .

# Первый коммит
git commit -m "Initial commit: Adaptive training bot MVP v1.0

- Garmin Connect integration
- Adaptive training plan (best practices)
- Google Calendar + ICS files for iPhone
- AI consultant (Claude API)
- Wellness survey (4 questions)
- Telegram bot with all commands
- Health check endpoint for Railway"

# Создать репозиторий на GitHub:
# Зайти на github.com → New repository → Название: training-bot
# НЕ СОЗДАВАТЬ README.md и .gitignore (уже есть)

# Добавить remote (замени <<USERNAME>> на свой GitHub username)
git remote add origin https://github.com/<<USERNAME>>/training-bot.git

# Отправить на GitHub
git branch -M main
git push -u origin main
```

### 2. Деплой на Railway

**Подробная инструкция:** [docs/railway_deployment.md](docs/railway_deployment.md)

**Кратко:**

1. Зайти на [railway.app](https://railway.app/) → Sign up / Login
2. **New Project** → **Deploy from GitHub repo**
3. Авторизовать Railway доступ к GitHub
4. Выбрать репозиторий `training-bot`
5. Railway автоматически деплоит проект

### 3. Настроить переменные окружения

Railway Dashboard → Settings → Variables → **Add Variable**

```
TELEGRAM_BOT_TOKEN=<<ВСТАВЬ_ТОКЕН>>
GARMIN_EMAIL=<<ВСТАВЬ_EMAIL>>
GARMIN_PASSWORD=<<ВСТАВЬ_PASSWORD>>
ANTHROPIC_API_KEY=<<ВСТАВЬ_API_KEY>>
DATABASE_PATH=/data/training_bot.db
TZ=Europe/Moscow
LOG_LEVEL=INFO
```

### 4. Добавить Railway Volume

Railway Dashboard → Settings → Volumes → **Add Volume**

- **Mount Path:** `/data`
- **Name:** `training-data`

Это сохранит базу данных между деплоями.

### 5. Загрузить Google Calendar токены

**Вариант A: Локально авторизоваться, потом загрузить токены**

```bash
# 1. Авторизоваться локально (откроется браузер)
cd bot_trainer
source venv/bin/activate
python -c "from src.integrations.calendar_sync import calendar_sync; calendar_sync.authenticate()"

# 2. Установить Railway CLI
npm i -g @railway/cli

# 3. Залогиниться в Railway
railway login

# 4. Подключить к проекту
railway link

# 5. Загрузить файлы
railway run bash -c 'cat > /data/credentials.json' < config/credentials.json
railway run bash -c 'cat > /data/token.json' < config/token.json
```

**Вариант B: Без CLI — через переменные окружения**

Добавить в Railway Variables:
```
GOOGLE_CREDENTIALS_JSON=<<СОДЕРЖИМОЕ config/credentials.json>>
GOOGLE_TOKEN_JSON=<<СОДЕРЖИМОЕ config/token.json>>
```

Потом в коде считывать и записывать в файлы.

### 6. Настроить UptimeRobot

1. Получить Railway URL:
   - Railway Dashboard → Settings → Domains → **Generate Domain**
   - Пример: `https://training-bot-production.up.railway.app`

2. Зайти на [uptimerobot.com](https://uptimerobot.com/) → Sign up / Login

3. **Add New Monitor**:
   - **Monitor Type:** HTTP(s)
   - **Friendly Name:** Training Bot
   - **URL:** `https://training-bot-production.up.railway.app/health`
   - **Monitoring Interval:** 5 minutes
   - Сохранить

### 7. Проверить деплой

**7.1 Проверить логи**

Railway Dashboard → Deployments → View Logs

Должно быть:
```
🏃 Запуск бота-тренера
✅ База данных инициализирована
✅ Health check сервер запущен на порту 8080
✅ Бот запущен: @your_bot_username
```

**7.2 Проверить health endpoint**

Открыть в браузере:
```
https://training-bot-production.up.railway.app/health
```

Должен вернуть:
```json
{
  "status": "healthy",
  "service": "training-bot",
  "uptime_seconds": 123
}
```

**7.3 Проверить бота в Telegram**

1. Открыть Telegram → найти своего бота
2. `/start` — приветствие
3. `/help` — список команд
4. `/sync` — синхронизация Garmin
5. `/plan` — план на неделю
6. `/stats` — статистика
7. `/calendar` — Google Calendar + ICS файл

---

## 📊 Чек-лист финального тестирования

После деплоя проверить:

- [ ] Бот отвечает на команды в Telegram
- [ ] `/sync` синхронизирует данные с Garmin
- [ ] `/plan` показывает план на неделю
- [ ] `/stats` показывает статистику (если есть данные)
- [ ] `/calendar` отправляет ICS файл
- [ ] ICS файл импортируется в iPhone Calendar одним кликом
- [ ] Вечерний опрос приходит в 00:00 MSK (если была тренировка вчера)
- [ ] Опрос проходится полностью (4 вопроса)
- [ ] После опроса приходит AI совет от тренера
- [ ] План автоматически адаптируется при пропусках
- [ ] Health check endpoint работает: `/health`
- [ ] UptimeRobot пингует каждые 5 минут
- [ ] Логи Railway не показывают ошибок

---

## 🐛 Troubleshooting

См. подробный раздел в [README.md](README.md#troubleshooting)

**Частые проблемы:**

1. **Бот не отвечает** → проверить `TELEGRAM_BOT_TOKEN`
2. **Garmin не синхронизируется** → проверить `GARMIN_EMAIL` и `GARMIN_PASSWORD`
3. **Google Calendar не работает** → загрузить `token.json` на Railway
4. **AI не даёт советов** → проверить `ANTHROPIC_API_KEY`
5. **Railway засыпает** → настроить UptimeRobot

---

## 📅 Timeline

**Сегодня (23.01):**
- [x] Подготовка к деплою завершена
- [ ] Создать GitHub репозиторий
- [ ] Деплой на Railway

**Завтра (24.01):**
- [ ] Настроить Google Calendar токены
- [ ] Настроить UptimeRobot
- [ ] Финальное тестирование

**Дедлайн MVP:** 01.02.2026 (за 2 недели до Tarki-Tau 50km)

---

## 💰 Стоимость

**Railway Free Tier:**
- $5 бесплатно в месяц
- Достаточно для 24/7 работы

**Claude API:**
- ~$0.10-0.50/месяц (лимит 10 запросов/день)

**ИТОГО:** ~$0-5/месяц (покрывается Free tier)

---

**Вопросы?** См. документацию:
- [README.md](README.md)
- [docs/railway_deployment.md](docs/railway_deployment.md)
- [docs/google_calendar_setup.md](docs/google_calendar_setup.md)
