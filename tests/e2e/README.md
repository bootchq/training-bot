# E2E Тестирование

**Рекомендуемый подход:** ручное тестирование по чек-листу.

---

## ✅ РЕКОМЕНДУЕТСЯ: Ручное тестирование

Используй подробную инструкцию: **[tests/MANUAL_TESTING.md](../MANUAL_TESTING.md)**

**Почему это лучше:**
- Не требует api_id/api_hash с my.telegram.org
- Проверяет реальное взаимодействие
- Занимает 3-5 минут
- Находит UX проблемы

**Быстрый чек-лист** (после каждого деплоя):
1. `/start` — отвечает ✅
2. Garmin регистрация — работает ✅
3. Онбординг "Забег → Трейл" — проходит ✅
4. `/reset` — очищает ✅

---

## Mock тесты (базовые)

**Плюсы:** не требует настройки
**Минусы:** не проверяет реальное взаимодействие

### Запуск

```bash
pytest tests/e2e/test_onboarding_mock.py -v
```

**Результат:** 3 passed ✅

---

## 2. Реальные тесты через Telethon (требует setup)

**Плюсы:** полная проверка как реальный пользователь
**Минусы:** требует api_id/api_hash с my.telegram.org

### Setup (один раз)

#### Шаг 1: Получить API credentials

1. Открой https://my.telegram.org
2. Авторизуйся по номеру телефона
3. Перейди в **API development tools**
4. Создай приложение:
   - App title: `E2E Tests`
   - Short name: `e2etests` (только буквы, без цифр)
   - Platform: `Desktop`
5. Скопируй **App api_id** и **App api_hash**

**Если выдает ERROR:**
- Попробуй другой short name: `bottest`, `testapp`, `myapp`
- Проверь что App title не пустой
- Если уже есть приложение — используй его api_id/api_hash

#### Шаг 2: Сгенерировать StringSession

```bash
cd "/Users/noor/Documents/Obsidian Vault/Бот тренера/bot_trainer"

# Замени 12345 и abcd... на свои значения
python3 scripts/generate_telethon_session.py 12345678 abcdef1234567890abcdef1234567890
```

Введи:
1. Номер телефона (в формате +7...)
2. Код из Telegram

Скопируй полученный **TELETHON_SESSION**.

#### Шаг 3: Создать .env.e2e

```bash
cp .env.e2e.example .env.e2e
```

Заполни:

```env
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
TELETHON_SESSION="1BVtsO..."
BOT_USERNAME=training_dag_run_bot
GARMIN_TEST_EMAIL=bootchq@gmail.com
GARMIN_TEST_PASSWORD=Aa1424617556
```

#### Шаг 4: Запуск тестов

```bash
pytest tests/e2e/test_onboarding_e2e.py -v
```

---

## Сравнение

| Критерий | Mock тесты | Telethon тесты |
|----------|------------|----------------|
| Setup | 0 минут | 5-10 минут |
| API credentials | Не нужны | Нужны |
| Проверка | Логика бота | Полный UX |
| Скорость | Быстро | Медленно |
| CI/CD | Да | Сложно |

---

## Рекомендации

1. **Локальная разработка:** используй mock тесты
2. **Перед деплоем:** запусти Telethon тесты вручную
3. **CI/CD:** настрой mock тесты в GitHub Actions

---

## Troubleshooting

### "API_ID и API_HASH обязательны"
- Проверь что заполнен `.env.e2e`
- Проверь что файл в корне `bot_trainer/`

### "Сессия невалидна"
- Перегенерируй через `scripts/generate_telethon_session.py`
- Проверь что TELETHON_SESSION скопирован полностью

### "Button not found"
- Проверь что бот запущен
- Проверь username бота в `.env.e2e`
- Добавь debug: `print(await get_button_texts(response))`

### "Timeout exceeded"
- Увеличь E2E_TIMEOUT в `.env.e2e` до 60
- Проверь интернет соединение
- Проверь что бот отвечает (ручной тест)
