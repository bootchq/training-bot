# Настройка Google Calendar API

> Связано: [ТЗ](../../ТЗ.md) | [Архитектура](../../Архитектура.md) | [Бэклог](../../Бэклог.md)

---


Пошаговая инструкция для интеграции бота с Google Calendar.

---

## Шаг 1: Создание проекта в Google Cloud Console

1. Открой [Google Cloud Console](https://console.cloud.google.com/)
2. Нажми **"Select a project"** → **"New Project"**
3. Название проекта: `Training Bot` (или любое другое)
4. Нажми **"Create"**

---

## Шаг 2: Включение Google Calendar API

1. В меню слева выбери **"APIs & Services"** → **"Enable APIs and Services"**
2. Найди в поиске: **"Google Calendar API"**
3. Нажми на него → **"Enable"**

---

## Шаг 3: Создание OAuth Credentials

1. Перейди в **"APIs & Services"** → **"Credentials"**
2. Нажми **"Create Credentials"** → **"OAuth client ID"**
3. Если появится экран "Configure Consent Screen":
   - Нажми **"Configure Consent Screen"**
   - Выбери **"External"** (если нет организации)
   - Заполни обязательные поля:
     - App name: `Training Bot`
     - User support email: твой email
     - Developer contact: твой email
   - Нажми **"Save and Continue"**
   - На экране "Scopes" просто нажми **"Save and Continue"**
   - На экране "Test users" добавь свой email
   - Нажми **"Save and Continue"**

4. Вернись в **"Credentials"** → **"Create Credentials"** → **"OAuth client ID"**
5. Application type: **"Desktop app"**
6. Name: `Training Bot Desktop`
7. Нажми **"Create"**

---

## Шаг 4: Скачивание credentials.json

1. После создания OAuth client появится окно с Client ID и Client Secret
2. Нажми **"Download JSON"**
3. Переименуй скачанный файл в `credentials.json`
4. Положи файл в папку: `bot_trainer/data/credentials.json`

```bash
mv ~/Downloads/client_secret_*.json bot_trainer/data/credentials.json
```

---

## Шаг 5: Первая авторизация

1. Запусти бота:
```bash
cd bot_trainer
source venv/bin/activate
python main.py
```

2. В Telegram отправь команду:
```
/calendar
```

3. Бот попросит авторизоваться:
   - Откроется браузер с запросом доступа к Google Calendar
   - Выбери свой аккаунт
   - Нажми **"Advanced"** (если появится предупреждение)
   - Нажми **"Go to Training Bot (unsafe)"**
   - Разрешить доступ к календарю

4. После успешной авторизации бот создаст файл `token.pickle`
5. В следующий раз авторизация не потребуется (токен обновляется автоматически)

---

## Шаг 6: Проверка работы

В Telegram отправь:
```
/calendar
```

Бот должен:
1. Создать события на неделю в твоём Google Calendar
2. Отправить сообщение: "✅ Синхронизация завершена"

---

## Устранение проблем

### Ошибка: "credentials.json не найден"
- Проверь, что файл лежит в `bot_trainer/data/credentials.json`
- Проверь права доступа: `chmod 644 bot_trainer/data/credentials.json`

### Ошибка: "Не удалось авторизоваться"
- Удали файл `token.pickle` и попробуй снова
- Проверь, что твой email добавлен в Test users в Google Cloud Console

### Ошибка: "Access blocked: This app's request is invalid"
- Убедись, что Google Calendar API включён
- Проверь, что OAuth consent screen настроен

### События не создаются
- Проверь логи: `cat bot.log`
- Убедись, что в плане есть тренировки на текущую неделю: `/plan`

---

## Структура файлов

```
bot_trainer/
├── data/
│   ├── credentials.json    # OAuth credentials (скачан из Google Cloud)
│   └── token.pickle        # Токен доступа (создаётся автоматически)
└── src/
    └── integrations/
        └── calendar_sync.py  # Модуль синхронизации
```

---

## Полезные ссылки

- [Google Cloud Console](https://console.cloud.google.com/)
- [Google Calendar API Docs](https://developers.google.com/calendar/api/guides/overview)
- [OAuth 2.0 for Desktop Apps](https://developers.google.com/identity/protocols/oauth2/native-app)
