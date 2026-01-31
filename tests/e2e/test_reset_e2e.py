"""E2E тест команды /reset"""
import pytest


@pytest.mark.asyncio
async def test_reset_command(client, bot, reset_bot):
    """Тест команды /reset - полный сброс данных"""

    # 1. Отправляем /reset
    async with client.conversation(bot, timeout=30) as conv:
        await conv.send_message("/reset")
        response = await conv.get_response()

        # Должна быть кнопка подтверждения
        assert response.buttons is not None, "Нет кнопок подтверждения"
        assert len(response.buttons) > 0, "Кнопки пусты"

        # Ищем кнопку "Да, сбросить"
        confirm_button = None
        for row in response.buttons:
            for button in row:
                if "сбросить" in button.text.lower():
                    confirm_button = button
                    break
            if confirm_button:
                break

        assert confirm_button is not None, f"Кнопка 'Да, сбросить' не найдена. Доступные: {[[b.text for b in row] for row in response.buttons]}"

        # 2. Нажимаем "Да, сбросить"
        await confirm_button.click()

        # Ждём подтверждения сброса
        confirmation = await conv.get_response()

        # Проверяем текст подтверждения
        assert "сброшены" in confirmation.text.lower() or "reset" in confirmation.text.lower(), \
            f"Некорректный текст подтверждения: {confirmation.text}"

        # 3. Проверяем, что можно начать заново
        await conv.send_message("/start")
        start_response = await conv.get_response()

        # Должна быть кнопка регистрации Garmin (т.е. онбординг начался с нуля)
        assert start_response.buttons is not None, "Нет кнопок в /start после reset"

        print("✅ Тест /reset пройден успешно")


@pytest.mark.asyncio
async def test_reset_cancel(client, bot, reset_bot):
    """Тест отмены команды /reset"""

    async with client.conversation(bot, timeout=30) as conv:
        await conv.send_message("/reset")
        response = await conv.get_response()

        # Ищем кнопку "Отмена"
        cancel_button = None
        for row in response.buttons:
            for button in row:
                if "отмен" in button.text.lower() or "нет" in button.text.lower():
                    cancel_button = button
                    break
            if cancel_button:
                break

        assert cancel_button is not None, "Кнопка отмены не найдена"

        # Нажимаем отмену
        await cancel_button.click()

        # Ждём подтверждения отмены
        confirmation = await conv.get_response()

        assert "отмен" in confirmation.text.lower(), \
            f"Некорректный текст отмены: {confirmation.text}"

        print("✅ Тест отмены /reset пройден успешно")
