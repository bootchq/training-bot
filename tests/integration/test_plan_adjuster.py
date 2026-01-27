"""Тесты для корректировщика плана тренировок"""
import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch
from src.core.plan_adjuster import PlanAdjuster


@pytest.fixture
def mock_db_session():
    """Мок сессии БД"""
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    return session


@pytest.mark.asyncio
async def test_analyze_no_missed_workouts():
    """Тест анализа когда нет пропусков"""
    adjuster = PlanAdjuster(user_id=999)

    with patch('src.core.plan_adjuster.db.get_session') as mock_get_session:
        session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = session

        # Мокаем 4 запланированные тренировки
        mock_planned = [
            MagicMock(date=date.today() - timedelta(days=i), type='easy', duration_min=60)
            for i in range(4)
        ]

        # И 4 фактические (все выполнены)
        mock_actual = [
            MagicMock(date=date.today() - timedelta(days=i))
            for i in range(4)
        ]

        session.query.return_value.filter.return_value.all.side_effect = [
            mock_planned,
            mock_actual
        ]

        result = adjuster.analyze_missed_workouts(weeks_back=1)

        assert result['total_planned'] == 4
        assert result['total_missed'] == 0
        assert result['miss_rate'] == 0


@pytest.mark.asyncio
async def test_analyze_some_missed_workouts():
    """Тест анализа с несколькими пропусками"""
    adjuster = PlanAdjuster(user_id=999)

    with patch('src.core.plan_adjuster.db.get_session') as mock_get_session:
        session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = session

        # 6 запланированных тренировок
        dates = [date.today() - timedelta(days=i) for i in range(6)]
        mock_planned = [
            MagicMock(date=d, type='easy' if i % 2 == 0 else 'long', duration_min=60)
            for i, d in enumerate(dates)
        ]

        # Только 4 фактические (2 пропущено)
        mock_actual = [
            MagicMock(date=dates[i])
            for i in [0, 1, 3, 4]  # пропущены индексы 2 и 5
        ]

        session.query.return_value.filter.return_value.all.side_effect = [
            mock_planned,
            mock_actual
        ]

        result = adjuster.analyze_missed_workouts(weeks_back=1)

        assert result['total_planned'] == 6
        assert result['total_missed'] == 2
        assert result['miss_rate'] == pytest.approx(33.33, rel=0.1)


@pytest.mark.asyncio
async def test_suggest_low_severity():
    """Тест рекомендаций при минимальных пропусках"""
    adjuster = PlanAdjuster(user_id=999)

    analysis = {
        'total_planned': 10,
        'total_missed': 1,
        'miss_rate': 10,  # 10% пропусков
        'missed_long': 0,
        'missed_intervals': 0
    }

    suggestions = adjuster.suggest_adjustments(analysis)

    assert suggestions['severity'] == 'low'
    assert 'continue_as_planned' in suggestions['actions']
    assert suggestions['volume_adjustment'] == 1.0


@pytest.mark.asyncio
async def test_suggest_moderate_severity():
    """Тест рекомендаций при умеренных пропусках"""
    adjuster = PlanAdjuster(user_id=999)

    analysis = {
        'total_planned': 10,
        'total_missed': 3,
        'miss_rate': 30,  # 30% пропусков
        'missed_long': 1,
        'missed_intervals': 1
    }

    suggestions = adjuster.suggest_adjustments(analysis)

    assert suggestions['severity'] == 'moderate'
    assert 'add_extra_long' in suggestions['actions']
    assert suggestions['volume_adjustment'] <= 1.0


@pytest.mark.asyncio
async def test_suggest_high_severity():
    """Тест рекомендаций при многих пропусках"""
    adjuster = PlanAdjuster(user_id=999)

    analysis = {
        'total_planned': 10,
        'total_missed': 5,
        'miss_rate': 50,  # 50% пропусков
        'missed_long': 2,
        'missed_intervals': 2
    }

    suggestions = adjuster.suggest_adjustments(analysis)

    assert suggestions['severity'] == 'high'
    assert 'reduce_volume' in suggestions['actions']
    assert suggestions['volume_adjustment'] < 1.0
    assert suggestions['volume_adjustment'] == 0.75


@pytest.mark.asyncio
async def test_adjust_future_plan_no_changes():
    """Тест что при continue_as_planned не меняем план"""
    adjuster = PlanAdjuster(user_id=999)

    adjustment = {
        'actions': ['continue_as_planned'],
        'volume_adjustment': 1.0
    }

    with patch('src.core.plan_adjuster.db.get_session'):
        result = adjuster.adjust_future_plan(adjustment)

        assert result == 0


@pytest.mark.asyncio
async def test_adjust_future_plan_reduce_volume():
    """Тест снижения объёма будущих тренировок"""
    adjuster = PlanAdjuster(user_id=999)

    adjustment = {
        'actions': ['reduce_volume'],
        'volume_adjustment': 0.75  # Снизить на 25%
    }

    with patch('src.core.plan_adjuster.db.get_session') as mock_get_session:
        session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = session

        # Создаем будущие тренировки
        future_date = date.today() + timedelta(days=2)
        mock_plan_1 = MagicMock(
            date=future_date,
            duration_min=60,
            distance_km=10.0,
            is_completed=False
        )
        mock_plan_2 = MagicMock(
            date=future_date + timedelta(days=2),
            duration_min=90,
            distance_km=15.0,
            is_completed=False
        )

        session.query.return_value.filter.return_value.all.return_value = [
            mock_plan_1,
            mock_plan_2
        ]

        result = adjuster.adjust_future_plan(adjustment)

        # Проверяем что изменено 2 тренировки
        assert result == 2

        # Проверяем корректировку первой тренировки: 60 * 0.75 = 45
        assert mock_plan_1.duration_min == 45

        # Проверяем корректировку второй тренировки: 90 * 0.75 = 67.5 -> 67
        assert mock_plan_2.duration_min == 67

        # Проверяем что БД зафиксирована
        session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_check_and_adjust_plan_integration():
    """Тест полного цикла анализ + корректировка"""
    adjuster = PlanAdjuster(user_id=999)

    with patch.object(adjuster, 'analyze_missed_workouts') as mock_analyze, \
         patch.object(adjuster, 'suggest_adjustments') as mock_suggest, \
         patch.object(adjuster, 'adjust_future_plan') as mock_adjust:

        mock_analyze.return_value = {'miss_rate': 30}
        mock_suggest.return_value = {'severity': 'moderate', 'actions': ['reduce_intensity']}
        mock_adjust.return_value = 3

        result = adjuster.check_and_adjust_plan()

        assert 'analysis' in result
        assert 'suggestions' in result
        assert 'adjusted_count' in result
        assert result['adjusted_count'] == 3

        mock_analyze.assert_called_once()
        mock_suggest.assert_called_once()
        mock_adjust.assert_called_once()
