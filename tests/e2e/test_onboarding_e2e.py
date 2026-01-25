"""
E2E тесты онбординга через Telethon.

Запуск:
    pytest tests/e2e/test_onboarding_e2e.py -v

Требования:
    1. Заполненный .env.e2e файл
    2. Работающий бот @training_dag_run_bot
"""

import asyncio
import pytest
from telethon import TelegramClient
from telethon.tl.types import ReplyInlineMarkup


async def click_button_by_text(response, text_contains: str) -> bool:
    """
    Кликает по кнопке, содержащей текст.
    Возвращает True если кнопка найдена и нажата.
    """
    if not response.buttons:
        return False

    for row in response.buttons:
        for button in row:
            if text_contains.lower() in button.text.lower():
                await button.click()
                return True
    return False


async def get_button_texts(response) -> list[str]:
    """Получить список текстов всех кнопок."""
    if not response.buttons:
        return []

    texts = []
    for row in response.buttons:
        for button in row:
            texts.append(button.text)
    return texts


@pytest.mark.asyncio
class TestOnboardingFlow:
    """Тесты полного flow онбординга."""

    async def test_start_shows_garmin_buttons(
        self,
        client: TelegramClient,
        bot_username: str,
        timeout: int,
        reset_bot
    ):
        """
        /start должен показывать кнопки Garmin.
        """
        async with client.conversation(bot_username, timeout=timeout) as conv:
            await conv.send_message("/start")
            response = await conv.get_response()

            buttons = await get_button_texts(response)
            print(f"Кнопки после /start: {buttons}")

            # Должны быть кнопки Garmin
            assert any("garmin" in b.lower() for b in buttons), \
                f"Кнопки Garmin не найдены. Найдены: {buttons}"

    async def test_garmin_registration_flow(
        self,
        client: TelegramClient,
        bot_username: str,
        garmin_credentials: tuple[str, str],
        timeout: int,
        message_wait: int,
        reset_bot
    ):
        """
        Тест регистрации Garmin: кнопка -> email -> password.
        """
        email, password = garmin_credentials
        if not email or not password:
            pytest.skip("Не заданы GARMIN_TEST_EMAIL и GARMIN_TEST_PASSWORD")

        async with client.conversation(bot_username, timeout=timeout) as conv:
            # /start
            await conv.send_message("/start")
            response = await conv.get_response()

            # Кликаем "Есть аккаунт Garmin"
            clicked = await click_button_by_text(response, "есть аккаунт")
            assert clicked, "Кнопка 'Есть аккаунт Garmin' не найдена"

            response = await conv.get_response()
            await asyncio.sleep(message_wait)

            # Вводим email
            await conv.send_message(email)
            response = await conv.get_response()
            await asyncio.sleep(message_wait)

            # Вводим password
            await conv.send_message(password)
            response = await conv.get_response()
            await asyncio.sleep(message_wait)

            # После Garmin должна быть кнопка онбординга
            buttons = await get_button_texts(response)
            print(f"Кнопки после Garmin: {buttons}")

            # Должна быть кнопка "Настроить тренировки"
            assert any("настроить" in b.lower() or "тренировки" in b.lower() for b in buttons), \
                f"Кнопка онбординга не найдена. Найдены: {buttons}"

    async def test_onboarding_goal_selection(
        self,
        client: TelegramClient,
        bot_username: str,
        garmin_credentials: tuple[str, str],
        timeout: int,
        message_wait: int,
        reset_bot
    ):
        """
        Тест выбора цели: "Подготовка к забегу" или "Тренировки для себя".
        """
        email, password = garmin_credentials
        if not email or not password:
            pytest.skip("Не заданы Garmin credentials")

        async with client.conversation(bot_username, timeout=timeout) as conv:
            # Проходим регистрацию Garmin
            await conv.send_message("/start")
            response = await conv.get_response()

            await click_button_by_text(response, "есть аккаунт")
            response = await conv.get_response()

            await conv.send_message(email)
            response = await conv.get_response()

            await conv.send_message(password)
            response = await conv.get_response()
            await asyncio.sleep(message_wait)

            # Кликаем "Настроить тренировки"
            clicked = await click_button_by_text(response, "настроить")
            if clicked:
                response = await conv.get_response()

            buttons = await get_button_texts(response)
            print(f"Кнопки выбора цели: {buttons}")

            # Проверяем что есть выбор цели
            has_race = any("забег" in b.lower() for b in buttons)
            has_fitness = any("для себя" in b.lower() for b in buttons)

            assert has_race or has_fitness, \
                f"Кнопки выбора цели не найдены. Найдены: {buttons}"

    async def test_race_type_selection(
        self,
        client: TelegramClient,
        bot_username: str,
        garmin_credentials: tuple[str, str],
        timeout: int,
        message_wait: int,
        reset_bot
    ):
        """
        Тест выбора типа забега после "Подготовка к забегу".
        """
        email, password = garmin_credentials
        if not email or not password:
            pytest.skip("Не заданы Garmin credentials")

        async with client.conversation(bot_username, timeout=timeout) as conv:
            # Проходим регистрацию Garmin
            await conv.send_message("/start")
            response = await conv.get_response()

            await click_button_by_text(response, "есть аккаунт")
            response = await conv.get_response()

            await conv.send_message(email)
            response = await conv.get_response()

            await conv.send_message(password)
            response = await conv.get_response()
            await asyncio.sleep(message_wait)

            # Кликаем "Настроить тренировки"
            if await click_button_by_text(response, "настроить"):
                response = await conv.get_response()

            # Кликаем "Подготовка к забегу"
            clicked = await click_button_by_text(response, "забегу")
            assert clicked, "Кнопка 'Подготовка к забегу' не найдена"

            response = await conv.get_response()
            buttons = await get_button_texts(response)
            print(f"Типы забега: {buttons}")

            # Проверяем что есть типы забега
            expected_types = ["полумарафон", "марафон", "трейл", "дистанц"]
            found = sum(1 for t in expected_types if any(t in b.lower() for b in buttons))

            assert found >= 2, \
                f"Типы забега не найдены. Ожидали минимум 2 из {expected_types}, найдены: {buttons}"

    async def test_trail_distance_input(
        self,
        client: TelegramClient,
        bot_username: str,
        garmin_credentials: tuple[str, str],
        timeout: int,
        message_wait: int,
        reset_bot
    ):
        """
        Тест ввода дистанции для трейла.
        """
        email, password = garmin_credentials
        if not email or not password:
            pytest.skip("Не заданы Garmin credentials")

        async with client.conversation(bot_username, timeout=timeout) as conv:
            # Проходим до выбора типа забега
            await conv.send_message("/start")
            response = await conv.get_response()

            await click_button_by_text(response, "есть аккаунт")
            response = await conv.get_response()

            await conv.send_message(email)
            response = await conv.get_response()

            await conv.send_message(password)
            response = await conv.get_response()
            await asyncio.sleep(message_wait)

            if await click_button_by_text(response, "настроить"):
                response = await conv.get_response()

            await click_button_by_text(response, "забегу")
            response = await conv.get_response()

            # Кликаем "Трейл"
            clicked = await click_button_by_text(response, "трейл")
            assert clicked, "Кнопка 'Трейл' не найдена"

            response = await conv.get_response()

            # Вводим дистанцию
            await conv.send_message("50")
            response = await conv.get_response()

            buttons = await get_button_texts(response)
            print(f"Кнопки после дистанции: {buttons}")

            # Должны показаться кнопки дней
            days = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
            found_days = sum(1 for d in days if any(d in b.lower() for b in buttons))

            assert found_days >= 5, \
                f"Кнопки дней не показаны. Найдены: {buttons}"

    async def test_days_selection(
        self,
        client: TelegramClient,
        bot_username: str,
        garmin_credentials: tuple[str, str],
        timeout: int,
        message_wait: int,
        reset_bot
    ):
        """
        Тест выбора дней тренировок.
        """
        email, password = garmin_credentials
        if not email or not password:
            pytest.skip("Не заданы Garmin credentials")

        async with client.conversation(bot_username, timeout=timeout) as conv:
            # Проходим до выбора дней
            await conv.send_message("/start")
            response = await conv.get_response()

            await click_button_by_text(response, "есть аккаунт")
            response = await conv.get_response()

            await conv.send_message(email)
            response = await conv.get_response()

            await conv.send_message(password)
            response = await conv.get_response()
            await asyncio.sleep(message_wait)

            if await click_button_by_text(response, "настроить"):
                response = await conv.get_response()

            await click_button_by_text(response, "забегу")
            response = await conv.get_response()

            await click_button_by_text(response, "трейл")
            response = await conv.get_response()

            await conv.send_message("50")
            response = await conv.get_response()

            # Выбираем Пн, Ср, Пт
            for day in ["Пн", "Ср", "Пт"]:
                await click_button_by_text(response, day)
                await asyncio.sleep(0.5)
                # После клика кнопки меняются (toggle), получаем новое состояние
                # НО НЕ новое сообщение - это edit_message_reply_markup

            # Кликаем "Готово"
            clicked = await click_button_by_text(response, "готово")
            assert clicked, "Кнопка 'Готово' не найдена"

            response = await conv.get_response()
            text = response.text.lower()

            # После выбора дней должен спросить время
            assert "врем" in text or "час" in text, \
                f"Не спросил время тренировки. Текст: {response.text}"

    async def test_full_onboarding_flow(
        self,
        client: TelegramClient,
        bot_username: str,
        garmin_credentials: tuple[str, str],
        timeout: int,
        message_wait: int,
        reset_bot
    ):
        """
        Полный тест онбординга от /start до завершения.
        """
        email, password = garmin_credentials
        if not email or not password:
            pytest.skip("Не заданы Garmin credentials")

        async with client.conversation(bot_username, timeout=timeout) as conv:
            print("\n=== ПОЛНЫЙ ТЕСТ ОНБОРДИНГА ===\n")

            # 1. /start
            print("1. /start")
            await conv.send_message("/start")
            response = await conv.get_response()
            print(f"   Ответ: {response.text[:100]}...")

            # 2. Garmin регистрация
            print("2. Garmin регистрация")
            await click_button_by_text(response, "есть аккаунт")
            response = await conv.get_response()

            await conv.send_message(email)
            response = await conv.get_response()

            await conv.send_message(password)
            response = await conv.get_response()
            await asyncio.sleep(message_wait)
            print(f"   Garmin: OK")

            # 3. Начало онбординга
            print("3. Начало онбординга")
            if await click_button_by_text(response, "настроить"):
                response = await conv.get_response()

            # 4. Выбор цели
            print("4. Выбор цели -> Забег")
            await click_button_by_text(response, "забегу")
            response = await conv.get_response()

            # 5. Тип забега -> Трейл
            print("5. Тип забега -> Трейл")
            await click_button_by_text(response, "трейл")
            response = await conv.get_response()

            # 6. Дистанция
            print("6. Дистанция -> 50 км")
            await conv.send_message("50")
            response = await conv.get_response()

            # 7. Выбор дней
            print("7. Выбор дней -> Пн, Ср, Пт")
            for day in ["Пн", "Ср", "Пт"]:
                await click_button_by_text(response, day)
                await asyncio.sleep(0.3)

            await click_button_by_text(response, "готово")
            response = await conv.get_response()

            # 8. Время
            print("8. Время -> 19:00")
            await conv.send_message("19:00")
            response = await conv.get_response()

            text = response.text.lower()
            print(f"   Финальный ответ: {response.text[:100]}...")

            # Проверяем успешное завершение
            assert "завершен" in text or "настройка" in text or "готов" in text, \
                f"Онбординг не завершился. Текст: {response.text}"

            print("\n=== ОНБОРДИНГ ЗАВЕРШЁН УСПЕШНО ===\n")


@pytest.mark.asyncio
class TestBotCommands:
    """Тесты отдельных команд бота."""

    async def test_help_command(
        self,
        client: TelegramClient,
        bot_username: str,
        timeout: int
    ):
        """Тест команды /help."""
        async with client.conversation(bot_username, timeout=timeout) as conv:
            await conv.send_message("/help")
            response = await conv.get_response()

            assert response.text, "/help не вернул текст"
            print(f"/help: {response.text[:100]}...")

    async def test_reset_command(
        self,
        client: TelegramClient,
        bot_username: str,
        timeout: int
    ):
        """Тест команды /reset."""
        async with client.conversation(bot_username, timeout=timeout) as conv:
            await conv.send_message("/reset")
            response = await conv.get_response()

            buttons = await get_button_texts(response)
            assert any("сбросить" in b.lower() for b in buttons), \
                f"Кнопка подтверждения сброса не найдена. Найдены: {buttons}"
