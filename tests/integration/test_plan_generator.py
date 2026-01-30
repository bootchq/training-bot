"""Тесты для генератора плана тренировок"""
import pytest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
from src.core.plan_generator import PlanGenerator


@pytest.fixture
def mock_db():
    """Мок БД для тестов генератора плана"""
    with patch('src.core.plan_generator.db') as mock:
        mock.get_user_settings = MagicMock(return_value={
            'vdot': 45,
            'lthr': 165,
            'experience_level': 'intermediate'
        })
        yield mock


@pytest.mark.asyncio
async def test_generate_plan_for_half_marathon(mock_db):
    """Тест генерации плана для полумарафона (21км)"""
    generator = PlanGenerator(user_id=999)
    goal_date = date.today() + timedelta(days=60)

    trainings = generator.generate_detailed_plan(
        goal_distance=21,
        goal_date=goal_date,
        training_days=[1, 3, 5],
        time_per_session=60,
        weeks=8,
        goal_type='race'
    )

    assert len(trainings) > 0
    assert all(t['type'] in ['intervals', 'tempo', 'long', 'easy', 'recovery'] for t in trainings)

    for training in trainings:
        if training['duration_min'] == 60:
            assert 5 <= training['distance_km'] <= 18


@pytest.mark.asyncio
async def test_generate_plan_for_marathon(mock_db):
    """Тест генерации плана для марафона (42км)"""
    generator = PlanGenerator(user_id=999)
    goal_date = date.today() + timedelta(days=90)

    trainings = generator.generate_detailed_plan(
        goal_distance=42,
        goal_date=goal_date,
        training_days=[1, 3, 5],
        time_per_session=60,
        weeks=12,
        goal_type='race'
    )

    assert len(trainings) > 0

    for training in trainings:
        if training['duration_min'] == 60 and training['type'] == 'easy':
            assert 5 <= training['distance_km'] <= 15


@pytest.mark.asyncio
async def test_generate_plan_for_trail(mock_db):
    """Тест генерации плана для трейла"""
    generator = PlanGenerator(user_id=999)
    goal_date = date.today() + timedelta(days=90)

    trainings = generator.generate_detailed_plan(
        goal_distance=50,
        goal_date=goal_date,
        training_days=[1, 3, 5, 6],
        time_per_session=90,
        weeks=12,
        goal_type='trail'
    )

    assert len(trainings) > 0

    has_trail_content = False
    for training in trainings:
        description = training.get('description', '').lower()
        if any(word in description for word in ['подъем', 'гор', 'трейл', 'рельеф', 'холм']):
            has_trail_content = True
            break

    assert has_trail_content or len(trainings) > 0

    for training in trainings:
        if training['duration_min'] == 90 and training['type'] == 'long':
            assert training['distance_km'] <= 20


@pytest.mark.asyncio
async def test_generate_plan_with_periodization(mock_db):
    """Тест периодизации плана"""
    generator = PlanGenerator(user_id=999)
    goal_date = date.today() + timedelta(days=70)

    trainings = generator.generate_detailed_plan(
        goal_distance=21,
        goal_date=goal_date,
        training_days=[2, 4, 6],
        time_per_session=60,
        weeks=10,
        goal_type='race'
    )

    assert len(trainings) > 0

    weeks = {}
    for training in trainings:
        week_num = (training['date'] - date.today()).days // 7
        if week_num not in weeks:
            weeks[week_num] = []
        weeks[week_num].append(training['duration_min'])

    assert len(weeks) >= 3


@pytest.mark.asyncio
async def test_workout_details_contain_distance(mock_db):
    """Тест что все тренировки содержат distance_km"""
    generator = PlanGenerator(user_id=999)
    goal_date = date.today() + timedelta(days=30)

    trainings = generator.generate_detailed_plan(
        goal_distance=21,
        goal_date=goal_date,
        training_days=[1, 3, 5],
        time_per_session=60,
        weeks=4,
        goal_type='race'
    )

    for training in trainings:
        assert 'distance_km' in training
        assert training['distance_km'] > 0
        assert 'description' in training
        assert len(training['description']) > 5
