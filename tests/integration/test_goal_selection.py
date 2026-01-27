"""Тесты для выбора цели (goal selection)"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.mark.asyncio
async def test_handle_goal_selection_race(bot, mock_update, mock_context):
    """Тест выбора цели: подготовка к забегу"""
    # Настройка мока
    mock_update.callback_query.data = "goal_race"

    # Мокаем БД методы
    with patch('src.bot.telegram_bot.db') as mock_db:
        mock_user = MagicMock(id=1)
        mock_db.get_or_create_user.return_value = mock_user
        mock_db.save_user_goal.return_value = None

        # Вызываем handler
        await bot.handle_goal_selection(mock_update, mock_context)

        # Проверки
        mock_update.callback_query.answer.assert_called_once()
        assert 'goal_type' in mock_context.user_data
        assert mock_context.user_data['goal_type'] == 'race'

        # Проверяем вызов БД
        mock_db.get_or_create_user.assert_called_once_with(12345)
        mock_db.save_user_goal.assert_called_once_with(1, goal_type='race')

        # Проверяем, что показаны кнопки выбора типа забега
        mock_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args
        assert "Какой тип забега?" in call_args[0][0]
        # Проверяем наличие reply_markup
        assert 'reply_markup' in call_args[1]


@pytest.mark.asyncio
async def test_handle_goal_selection_fitness(bot, mock_update, mock_context):
    """Тест выбора цели: тренировки для себя"""
    # Настройка мока
    mock_update.callback_query.data = "goal_fitness"

    # Мокаем БД и метод показа дней
    with patch('src.bot.telegram_bot.db') as mock_db, \
         patch.object(bot, '_show_days_selection', new_callable=AsyncMock) as mock_show_days:

        mock_user = MagicMock(id=1)
        mock_db.get_or_create_user.return_value = mock_user
        mock_db.save_user_goal.return_value = None

        # Вызываем handler
        await bot.handle_goal_selection(mock_update, mock_context)

        # Проверки
        mock_update.callback_query.answer.assert_called_once()
        assert 'goal_type' in mock_context.user_data
        assert mock_context.user_data['goal_type'] == 'fitness'

        # Проверяем вызов БД
        mock_db.get_or_create_user.assert_called_once_with(12345)
        mock_db.save_user_goal.assert_called_once_with(1, goal_type='fitness')

        # Проверяем, что сразу показан выбор дней (для fitness пропускаем выбор типа забега)
        mock_show_days.assert_called_once()


@pytest.mark.asyncio
async def test_handle_goal_selection_saves_to_context(bot, mock_update, mock_context):
    """Тест сохранения goal_type в context.user_data"""
    mock_update.callback_query.data = "goal_race"

    with patch('src.bot.telegram_bot.db') as mock_db:
        mock_user = MagicMock(id=1)
        mock_db.get_or_create_user.return_value = mock_user

        # До вызова user_data пуст
        assert 'goal_type' not in mock_context.user_data

        await bot.handle_goal_selection(mock_update, mock_context)

        # После вызова goal_type должен быть в user_data
        assert 'goal_type' in mock_context.user_data
        assert mock_context.user_data['goal_type'] == 'race'
