# 🏃 Бот-тренер по бегу

Адаптивный Telegram-бот с AI-консультантом для подготовки к марафону и трейлам.

**Версия:** 1.0 (MVP)
**Статус:** Ready for deployment
**Дата:** 23.01.2026

---

## О проекте

Этот бот помогает готовиться к беговым гонкам, автоматически адаптируя тренировочный план на основе:
- Фактического выполнения тренировок (данные из Garmin Connect)
- Самочувствия спортсмена (ежедневный опрос)
- AI-анализа тренировок (Claude Sonnet 3.5)

**Цели проекта:**
- Подготовка к Tarki-Tau 50km (15-16.02.2026)
- Marathon 42km (Середина марта 2026)
- DWT 65km (Середина апреля 2026)

**Принципы адаптации (на основе best practices):**
- 1-2 пропуска — план не меняется
- 3+ пропуска — перераспределение 50-75% объёма
- Wellness monitoring — комбинированный подход (HRV + опросы)
- Приоритизация важных тренировок (tempo, intervals, long runs)

## Возможности

- Автоматическая синхронизация с Garmin Connect
- Адаптивный план тренировок
- Интеграция с Google Calendar
- AI-советы после каждой тренировки
- Вечерний опрос о самочувствии
- Статистика и прогресс

## Требования

- Python 3.9+
- Аккаунт Garmin Connect
- Telegram Bot Token (от @BotFather)
- Claude API ключ (рекомендуемо) или OpenAI API

## Быстрый старт

### 1. Установка зависимостей

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Настройка переменных окружения

Скопируйте `.env.example` в `.env` и заполните:

```bash
cp .env.example .env
nano .env
```

**Обязательные:**
- `TELEGRAM_BOT_TOKEN` — токен от @BotFather
- `GARMIN_EMAIL` и `GARMIN_PASSWORD` — данные Garmin Connect
- `ANTHROPIC_API_KEY` — API-ключ Claude

**Опциональные:**
- Google Calendar credentials (для синхронизации плана)

### 3. Инициализация базы данных

```bash
python src/database/init_db.py
```

### 4. Запуск бота

```bash
python main.py
```

## Структура проекта

```
bot_trainer/
├── src/
│   ├── bot/              # Telegram-бот
│   ├── core/             # Логика адаптации
│   ├── integrations/     # Garmin, Calendar, AI
│   ├── database/         # SQLite ORM
│   └── utils/            # Утилиты
├── data/                 # База данных
├── config/               # Конфигурация
├── tests/                # Тесты
└── main.py               # Точка входа
```

## Команды бота

- `/start` — Приветствие и описание возможностей
- `/help` — Справка по командам
- `/sync` — Ручная синхронизация с Garmin
- `/stats` — Статистика за неделю/месяц
- `/plan` — План тренировок на неделю
- `/calendar` — Синхронизация с Google Calendar + ICS файл

## Автоматические функции

- **00:00 MSK** — Синхронизация Garmin → Анализ выполнения → Адаптация плана → Вечерний опрос (если была тренировка) → AI совет
- **01:00 MSK** — Отправка плана на неделю + ICS файл для iPhone Calendar

## Разработка

### Запуск тестов

```bash
pytest tests/
```

### Логи

Логи сохраняются в `logs/bot.log`

## Архитектура

### Модули

**`src/bot/`** — Telegram-бот (python-telegram-bot 20.7)
- `telegram_bot.py` — Обработчики команд и callback'ов

**`src/core/`** — Логика тренировочного плана
- `plan_adapter.py` — Адаптация плана при пропусках/перевыполнении
- `scheduler.py` — Расписание (синхронизация, опросы, план на неделю)
- `wellness_survey.py` — Вечерний опрос из 4 вопросов

**`src/integrations/`** — Внешние сервисы
- `garmin_sync.py` — Синхронизация с Garmin Connect
- `calendar_sync.py` — Google Calendar + ICS файлы для iPhone
- `plan_parser.py` — Парсинг тренировочного плана из Markdown

**`src/ai/`** — AI-консультант
- `consultant.py` — Интеграция с Claude API (лимит 10 запросов/день)

**`src/database/`** — База данных (SQLAlchemy 2.0 + SQLite)
- `db.py` — ORM модели и CRUD операции
- `init_db.py` — Инициализация схемы БД

**`src/utils/`** — Утилиты
- `config.py` — Конфигурация из .env
- `logger.py` — Логирование (ротация, уровни)
- `health_check.py` — HTTP сервер для Railway keep-alive

### База данных

**Таблицы:**
- `users` — Пользователи (Telegram ID, настройки)
- `trainings` — Фактические тренировки (из Garmin)
- `training_plan` — Плановые тренировки
- `wellness_surveys` — Опросы самочувствия
- `goals` — Цели (даты гонок, целевое время)

## Деплой

См. подробную инструкцию: [docs/railway_deployment.md](docs/railway_deployment.md)

**Кратко:**
1. Загрузить код на GitHub
2. Создать проект на Railway
3. Настроить переменные окружения
4. Добавить Railway Volume для `/data`
5. Настроить UptimeRobot для keep-alive
6. Протестировать основные сценарии

## Troubleshooting

### Бот не отвечает на команды
- Проверить `TELEGRAM_BOT_TOKEN` в `.env`
- Убедиться что бот не запущен в другом месте
- Проверить логи: `tail -f logs/bot.log`

### Garmin синхронизация не работает
- Проверить `GARMIN_EMAIL` и `GARMIN_PASSWORD`
- Garmin может требовать капчу при первом входе
- Попробовать вручную: `/sync` в Telegram

### Google Calendar не синхронизируется
- Проверить что `credentials.json` существует в `config/`
- Первый раз нужно авторизоваться (см. [docs/google_calendar_setup.md](docs/google_calendar_setup.md))
- Токен обновляется автоматически

### AI советы не приходят
- Проверить `ANTHROPIC_API_KEY` в `.env`
- Проверить лимит запросов (10/день на пользователя)
- При превышении лимита — шаблонные советы

## Документация

- [Архитектура](../Инфраструктура/{bot-trainer} {spec} Архитектура.md) — Детальная архитектура решения
- [Бэклог](../Инфраструктура/{bot-trainer} {spec} Бэклог.md) — Задачи и прогресс разработки
- [ТЗ](../Инфраструктура/{bot-trainer} {spec} ТЗ.md) — Требования и зафиксированные решения
- [Google Calendar Setup](docs/google_calendar_setup.md) — Настройка Google OAuth
- [Railway Deployment](docs/railway_deployment.md) — Деплой на Railway

## Лицензия

MIT

---

**Следующие шаги:**
- [ ] Деплой на Railway
- [ ] Тестирование в продакшене
- [ ] Мониторинг и оптимизация

**Post-MVP идеи:**
- Графики статистики (объёмы, пульс, зоны)
- Создание плана с нуля (AI-генерация)
- Интеграция Strava
- Мультиязычность (EN)
