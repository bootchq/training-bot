# 🚀 Деплой на Railway

Пошаговая инструкция по развёртыванию бота-тренера на платформе Railway.

---

## Предварительные требования

1. **GitHub аккаунт** - для хранения кода
2. **Railway аккаунт** - регистрация на [railway.app](https://railway.app/)
3. **Все токены и API-ключи:**
   - Telegram Bot Token (от @BotFather)
   - Garmin email и password
   - Google Calendar credentials.json
   - Claude API key (Anthropic)

---

## Шаг 1: Подготовка GitHub репозитория

### 1.1 Создать репозиторий на GitHub

```bash
# Инициализировать git (если ещё не сделано)
cd bot_trainer
git init

# Добавить все файлы
git add .

# Первый коммит
git commit -m "Initial commit: Adaptive training bot MVP"

# Создать репозиторий на GitHub и добавить remote
git remote add origin https://github.com/<<ВАШ_USERNAME>>/training-bot.git

# Отправить код на GitHub
git branch -M main
git push -u origin main
```

### 1.2 Проверить .gitignore

Убедитесь что `.gitignore` **НЕ включает** в репозиторий:
- `.env` (секреты)
- `*.db` (база данных)
- `token.json`, `token.pickle` (Google OAuth токены)
- `credentials.json` (Google Calendar credentials)
- `data/`, `logs/`

---

## Шаг 2: Развёртывание на Railway

### 2.1 Создать проект на Railway

1. Зайти на [railway.app](https://railway.app/)
2. Нажать **"New Project"**
3. Выбрать **"Deploy from GitHub repo"**
4. Авторизовать Railway доступ к GitHub
5. Выбрать репозиторий `training-bot`

### 2.2 Настроить переменные окружения

В Railway Dashboard → Settings → Variables добавить:

```bash
# Telegram
TELEGRAM_BOT_TOKEN=<<ВСТАВЬ_ТОКЕН_ОТ_BOTFATHER>>

# Garmin
GARMIN_EMAIL=<<ВСТАВЬ_EMAIL>>
GARMIN_PASSWORD=<<ВСТАВЬ_PASSWORD>>

# Google Calendar (будет настроено позже)
# GOOGLE_CREDENTIALS_PATH и GOOGLE_TOKEN_PATH не нужны на Railway
# Вместо этого используем Railway Volumes (см. Шаг 3)

# AI
ANTHROPIC_API_KEY=<<ВСТАВЬ_API_KEY>>

# Database
DATABASE_PATH=/data/training_bot.db

# Timezone
TZ=Europe/Moscow

# Logging
LOG_LEVEL=INFO

# Port (Railway автоматически установит)
# PORT будет установлен автоматически
```

### 2.3 Добавить Railway Volume для данных

Railway не сохраняет данные между деплоями. Нужно создать Volume:

1. Railway Dashboard → Settings → Volumes
2. Нажать **"Add Volume"**
3. Задать:
   - **Mount Path:** `/data`
   - **Name:** `training-data`
4. Сохранить

Теперь база данных будет сохраняться между деплоями.

---

## Шаг 3: Настройка Google Calendar на Railway

Google OAuth требует ручную авторизацию первый раз. На Railway это сложно сделать.

### Решение: Авторизоваться локально, загрузить токены на Railway

#### 3.1 Локальная авторизация

```bash
# На локальной машине
cd bot_trainer

# Запустить скрипт авторизации
python -c "
from src.integrations.calendar_sync import calendar_sync
calendar_sync.authenticate()
print('Токен сохранён в config/token.json')
"
```

Откроется браузер для авторизации Google Calendar.

#### 3.2 Загрузка токенов на Railway

**Вариант A: Через Railway CLI**

```bash
# Установить Railway CLI
npm i -g @railway/cli

# Логин в Railway
railway login

# Перейти в проект
railway link

# Загрузить credentials.json
railway run echo "$(cat config/credentials.json)" > /data/credentials.json

# Загрузить token.json
railway run echo "$(cat config/token.json)" > /data/token.json
```

**Вариант B: Через переменные окружения (не рекомендуется, т.к. JSON)**

Можно добавить содержимое файлов как переменные:

```bash
GOOGLE_CREDENTIALS_JSON='{"installed":{"client_id":"...","client_secret":"..."}}'
GOOGLE_TOKEN_JSON='{"token":"...","refresh_token":"..."}'
```

Потом в коде считывать из ENV и записывать в файлы.

---

## Шаг 4: Настройка Keep-Alive (UptimeRobot)

Railway может засыпать если нет активности. Настраиваем пинги.

### 4.1 Получить URL Railway проекта

Railway Dashboard → Settings → Domains → **Generate Domain**

Получите URL типа: `https://training-bot-production.up.railway.app`

### 4.2 Настроить UptimeRobot

1. Зайти на [uptimerobot.com](https://uptimerobot.com/)
2. Создать **новый монитор**:
   - **Monitor Type:** HTTP(s)
   - **Friendly Name:** Training Bot
   - **URL:** `https://training-bot-production.up.railway.app/health`
   - **Monitoring Interval:** 5 minutes
3. Сохранить

Теперь UptimeRobot будет пинговать `/health` endpoint каждые 5 минут.

---

## Шаг 5: Проверка деплоя

### 5.1 Проверить логи

Railway Dashboard → Deployments → View Logs

Должно быть:
```
🏃 Запуск бота-тренера
✅ База данных инициализирована
✅ Health check сервер запущен на порту 8080
✅ Бот запущен: @your_bot_username
```

### 5.2 Проверить health check

Открыть в браузере:
```
https://training-bot-production.up.railway.app/health
```

Должен вернуть JSON:
```json
{
  "status": "healthy",
  "service": "training-bot",
  "uptime_seconds": 123,
  "timestamp": "2026-01-23T12:00:00"
}
```

### 5.3 Проверить бота в Telegram

1. Открыть Telegram, найти своего бота
2. Отправить `/start`
3. Проверить команды:
   - `/help` - список команд
   - `/stats` - статистика (если есть данные)
   - `/plan` - план на неделю

---

## Шаг 6: Тестирование основных сценариев

### 6.1 Ручная синхронизация Garmin

```
/sync
```

Должно прийти сообщение:
```
✅ Синхронизация завершена
Загружено тренировок: X
```

### 6.2 Проверка плана

```
/plan
```

Должен прийти план на неделю в формате:
```
📅 План на неделю (23.01 - 29.01)

ПН 23.01: Лёгкая 8 км (Z1-Z2)
ВТ 24.01: Темповая 12 км (Z3)
...
```

### 6.3 Проверка Google Calendar

```
/calendar
```

Должно прийти:
- Сообщение "✅ План синхронизирован с Google Calendar"
- ICS файл для импорта в iPhone Calendar

### 6.4 Проверка вечернего опроса (автоматически)

Опрос придёт в 00:00 MSK **только если была тренировка** вчера.

Формат:
```
📋 Опрос после тренировки (22.01)

❓ Как оцениваешь тренировку?
(1 - плохо, 10 - отлично)

[кнопки 1-10]
```

После завершения опроса придёт **AI совет от тренера**.

---

## Шаг 7: Мониторинг и отладка

### 7.1 Логи Railway

Railway Dashboard → Logs

Фильтровать по уровням:
- `INFO` - обычные события
- `WARNING` - предупреждения
- `ERROR` - ошибки

### 7.2 Проверка БД

Если нужно проверить данные в БД:

```bash
# Railway CLI
railway run python -c "
from src.database.db import db
users = db.get_all_users()
print(f'Пользователей: {len(users)}')
"
```

### 7.3 Перезапуск бота

Railway Dashboard → Deployments → **Restart**

---

## Частые проблемы и решения

### Проблема 1: Бот не отвечает на команды

**Решение:**
- Проверить что `TELEGRAM_BOT_TOKEN` правильный
- Проверить логи Railway на наличие ошибок
- Убедиться что бот не запущен в другом месте (конфликт webhooks)

### Проблема 2: Garmin синхронизация не работает

**Решение:**
- Проверить `GARMIN_EMAIL` и `GARMIN_PASSWORD`
- Garmin может требовать капчу при первом входе с нового IP
- Попробовать вручную: `/sync`

### Проблема 3: Google Calendar не синхронизируется

**Решение:**
- Убедиться что `credentials.json` и `token.json` загружены на Railway
- Проверить что токен не истёк (refresh token работает автоматически)
- Проверить логи на наличие OAuth ошибок

### Проблема 4: Railway засыпает

**Решение:**
- Убедиться что UptimeRobot настроен и пингует `/health`
- Проверить что health check сервер работает:
  ```
  https://your-app.railway.app/health
  ```

### Проблема 5: БД пустая после редеплоя

**Решение:**
- Убедиться что Railway Volume настроен (`/data`)
- `DATABASE_PATH` должен указывать на `/data/training_bot.db`

---

## Стоимость Railway

**Free tier (Hobby Plan):**
- $5 бесплатно в месяц
- ~500 часов работы (достаточно для 24/7 если 1 сервис)
- 1 GB RAM
- 1 GB storage

**Примерная стоимость этого проекта:**
- **Без нагрузки:** ~$5/месяц (покрывается Free tier)
- **С AI запросами:** +$0.10-0.50/месяц (зависит от лимита 10 запросов/день)

**Экономия:**
- Использовать Free tier Railway
- Лимит AI запросов (10/день) экономит на Claude API
- Health check каждые 5 минут (не чаще)

---

## Обновление кода

При изменении кода:

```bash
# Локально
git add .
git commit -m "Update: описание изменений"
git push origin main
```

Railway **автоматически** задеплоит новую версию.

---

## Бэкап данных

Рекомендуется регулярно делать бэкап БД:

```bash
# Railway CLI
railway run cat /data/training_bot.db > backup_$(date +%Y%m%d).db
```

Или настроить автоматический бэкап через Railway Cron Jobs.

---

## Полезные ссылки

- [Railway Docs](https://docs.railway.app/)
- [Railway CLI](https://docs.railway.app/develop/cli)
- [UptimeRobot Docs](https://uptimerobot.com/api/)
- [Telegram Bot API](https://core.telegram.org/bots/api)

---

## Чек-лист финального деплоя

- [ ] Код загружен на GitHub
- [ ] Railway проект создан и подключён к репозиторию
- [ ] Все переменные окружения настроены
- [ ] Railway Volume создан для `/data`
- [ ] Google Calendar токены загружены
- [ ] Health check endpoint работает (`/health`)
- [ ] UptimeRobot настроен для пингов
- [ ] Бот отвечает на команды в Telegram
- [ ] Garmin синхронизация работает (`/sync`)
- [ ] План показывается (`/plan`)
- [ ] Google Calendar синхронизируется (`/calendar`)
- [ ] Вечерний опрос приходит в 00:00 (если была тренировка)
- [ ] AI советы приходят после опроса

---

**Дата обновления:** 2026-01-23
**Версия:** 1.0
**Статус:** MVP ready for deployment
