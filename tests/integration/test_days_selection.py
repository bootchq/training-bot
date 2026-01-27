"""Тесты для выбора дней тренировок (days selection)"""
import pytest
from unittest.mock import MagicMock, patch


@pytest.mark.asyncio
async def test_handle_days_selection_add_day(bot, mock_update, mock_context):
    """Тест добавления дня в выбранные"""
    mock_update.callback_query.data = "trainday_1"  # Понедельник
    mock_context.user_data['selected_days'] = []

    with patch('src.bot.telegram_bot.db') as mock_db:
        mock_user = MagicMock(id=1)
        mock_db.get_or_create_user.return_value = mock_user

        await bot.handle_days_selection(mock_update, mock_context)

        # Проверяем, что день добавлен
        assert 1 in mock_context.user_data['selected_days']
        assert len(mock_context.user_data['selected_days']) == 1

        # Проверяем, что кнопки обновлены
        mock_update.callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_handle_days_selection_remove_day(bot, mock_update, mock_context):
    """Тест удаления дня из выбранных (toggle off)"""
    mock_update.callback_query.data = "trainday_1"  # Понедельник
    mock_context.user_data['selected_days'] = [1, 3]  # Уже выбраны Пн и Ср

    with patch('src.bot.telegram_bot.db') as mock_db:
        mock_user = MagicMock(id=1)
        mock_db.get_or_create_user.return_value = mock_user

        await bot.handle_days_selection(mock_update, mock_context)

        # Проверяем, что день 1 удален
        assert 1 not in mock_context.user_data['selected_days']
        assert 3 in mock_context.user_data['selected_days']
        assert len(mock_context.user_data['selected_days']) == 1


@pytest.mark.asyncio
async def test_handle_days_selection_multiple_days(bot, mock_update, mock_context):
    """Тест выбора нескольких дней"""
    mock_context.user_data['selected_days'] = []

    with patch('src.bot.telegram_bot.db') as mock_db:
        mock_user = MagicMock(id=1)
        mock_db.get_or_create_user.return_value = mock_user

        # Выбираем понедельник
        mock_update.callback_query.data = "trainday_1"
        await bot.handle_days_selection(mock_update, mock_context)
        assert 1 in mock_context.user_data['selected_days']

        # Выбираем среду
        mock_update.callback_query.data = "trainday_3"
        await bot.handle_days_selection(mock_update, mock_context)
        assert 3 in mock_context.user_data['selected_days']

        # Выбираем пятницу
        mock_update.callback_query.data = "trainday_5"
        await bot.handle_days_selection(mock_update, mock_context)
        assert 5 in mock_context.user_data['selected_days']

        # Всего 3 дня
        assert len(mock_context.user_data['selected_days']) == 3
        assert mock_context.user_data['selected_days'] == [1, 3, 5]


@pytest.mark.asyncio
async def test_handle_days_done_insufficient(bot, mock_update, mock_context):
    """Тест нажатия 'Готово' с менее чем 2 днями - должен показать alert"""
    mock_update.callback_query.data = "trainday_done"
    mock_context.user_data['selected_days'] = [1]  # Только 1 день

    with patch('src.bot.telegram_bot.db') as mock_db:
        mock_user = MagicMock(id=1)
        mock_db.get_or_create_user.return_value = mock_user

        await bot.handle_days_selection(mock_update, mock_context)

        # Проверяем, что показан alert
        mock_update.callback_query.answer.assert_called()
        call_args = mock_update.callback_query.answer.call_args
        assert "минимум 2 дня" in call_args[0][0]
        assert call_args[1]['show_alert'] is True

        # БД НЕ вызвана
        mock_db.save_user_goal.assert_not_called()


@pytest.mark.asyncio
async def test_handle_days_done_sufficient(bot, mock_update, mock_context):
    """Тест нажатия 'Готово' с 2+ днями - должен сохранить и спросить время"""
    mock_update.callback_query.data = "trainday_done"
    mock_context.user_data['selected_days'] = [1, 3, 5]  # 3 дня
    mock_context.user_data['goal_type'] = 'race'

    with patch('src.bot.telegram_bot.db') as mock_db:
        mock_user = MagicMock(id=1)
        mock_db.get_or_create_user.return_value = mock_user

        await bot.handle_days_selection(mock_update, mock_context)

        # Проверяем, что дни сохранены в БД
        mock_db.save_user_goal.assert_called_once_with(
            1,
            goal_type='race',
            training_days=['day_1', 'day_3', 'day_5']
        )

        # Проверяем, что показан запрос времени
        mock_update.callback_query.message.reply_text.assert_called_once()
        call_args = mock_update.callback_query.message.reply_text.call_args
        assert "В какое время" in call_args[0][0]

        # Проверяем, что установлен флаг ожидания времени
        assert mock_context.user_data.get('awaiting_time') is True


@pytest.mark.asyncio
async def test_handle_days_done_default_goal_type(bot, mock_update, mock_context):
    """Тест использования default goal_type если не указан"""
    mock_update.callback_query.data = "trainday_done"
    mock_context.user_data['selected_days'] = [2, 4]  # 2 дня
    # goal_type НЕ указан - должен быть 'fitness' по умолчанию

    with patch('src.bot.telegram_bot.db') as mock_db:
        mock_user = MagicMock(id=1)
        mock_db.get_or_create_user.return_value = mock_user

        await bot.handle_days_selection(mock_update, mock_context)

        # Проверяем, что использован 'fitness' по умолчанию
        mock_db.save_user_goal.assert_called_once_with(
            1,
            goal_type='fitness',  # default
            training_days=['day_2', 'day_4']
        )
