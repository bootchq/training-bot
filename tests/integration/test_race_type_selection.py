"""Тесты для выбора типа забега (race type selection)"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.mark.asyncio
async def test_handle_race_type_half(bot, mock_update, mock_context):
    """Тест выбора полумарафона (21 км)"""
    mock_update.callback_query.data = "racetype_half"
    
    with patch('src.bot.telegram_bot.db') as mock_db, \
         patch.object(bot, '_ask_goal_date', new_callable=AsyncMock) as mock_ask_date:

        mock_user = MagicMock(id=1)
        mock_db.get_or_create_user.return_value = mock_user

        await bot.handle_race_type_selection(mock_update, mock_context)

        # Проверки
        mock_update.callback_query.answer.assert_called_once()
        mock_db.save_user_goal.assert_called_once_with(1, goal_type='race', goal_distance_km=21)
        assert mock_context.user_data['goal_type'] == 'race'
        mock_ask_date.assert_called_once()


@pytest.mark.asyncio
async def test_handle_race_type_marathon(bot, mock_update, mock_context):
    """Тест выбора марафона (42 км)"""
    mock_update.callback_query.data = "racetype_marathon"
    
    with patch('src.bot.telegram_bot.db') as mock_db, \
         patch.object(bot, '_ask_goal_date', new_callable=AsyncMock) as mock_ask_date:

        mock_user = MagicMock(id=1)
        mock_db.get_or_create_user.return_value = mock_user

        await bot.handle_race_type_selection(mock_update, mock_context)

        # Проверки
        mock_update.callback_query.answer.assert_called_once()
        mock_db.save_user_goal.assert_called_once_with(1, goal_type='race', goal_distance_km=42)
        assert mock_context.user_data['goal_type'] == 'race'
        mock_ask_date.assert_called_once()


@pytest.mark.asyncio
async def test_handle_race_type_custom(bot, mock_update, mock_context):
    """Тест выбора своей дистанции"""
    mock_update.callback_query.data = "racetype_custom"
    
    with patch('src.bot.telegram_bot.db') as mock_db:
        mock_user = MagicMock(id=1)
        mock_db.get_or_create_user.return_value = mock_user

        await bot.handle_race_type_selection(mock_update, mock_context)

        # Проверки
        mock_update.callback_query.answer.assert_called_once()
        assert mock_context.user_data['goal_type'] == 'race'
        assert mock_context.user_data.get('awaiting_custom_distance') is True

        # Проверяем, что показано сообщение с просьбой ввести дистанцию
        mock_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args
        assert "Введи дистанцию забега" in call_args[0][0]


@pytest.mark.asyncio
async def test_handle_race_type_trail(bot, mock_update, mock_context):
    """Тест выбора трейла"""
    mock_update.callback_query.data = "racetype_trail"
    
    with patch('src.bot.telegram_bot.db') as mock_db:
        mock_user = MagicMock(id=1)
        mock_db.get_or_create_user.return_value = mock_user

        await bot.handle_race_type_selection(mock_update, mock_context)

        # Проверки
        mock_update.callback_query.answer.assert_called_once()
        assert mock_context.user_data['goal_type'] == 'trail'
        assert mock_context.user_data.get('awaiting_trail_distance') is True

        # Проверяем, что показано сообщение с просьбой ввести дистанцию трейла
        mock_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args
        assert "Введи дистанцию трейла" in call_args[0][0]


@pytest.mark.asyncio
async def test_handle_race_type_unknown(bot, mock_update, mock_context):
    """Тест обработки неизвестного типа забега"""
    mock_update.callback_query.data = "racetype_unknown"
    
    with patch('src.bot.telegram_bot.db') as mock_db:
        mock_user = MagicMock(id=1)
        mock_db.get_or_create_user.return_value = mock_user

        await bot.handle_race_type_selection(mock_update, mock_context)

        # Проверяем, что показано сообщение об ошибке
        mock_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args
        assert "Устаревшее сообщение" in call_args[0][0]
        assert "/reset" in call_args[0][0]
