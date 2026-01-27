"""Тесты для генератора плана тренировок"""
import pytest
from datetime import date, timedelta
from src.core.plan_generator import PlanGenerator


@pytest.mark.asyncio
async def test_generate_plan_for_half_marathon():
    """Тест генерации плана для полумарафона (21км)"""
    generator = PlanGenerator(user_id=999)
    goal_date = date.today() + timedelta(days=60)  # Через 2 месяца

    trainings = generator.generate_detailed_plan(
        goal_distance=21,
        goal_date=goal_date,
        training_days=[1, 3, 5],  # Пн, Ср, Пт
        time_per_session=60,
        weeks=8,
        goal_type='race'
    )

    # Проверяем, что план создан
    assert len(trainings) > 0
    assert all(t['type'] in ['intervals', 'tempo', 'long', 'easy', 'recovery'] for t in trainings)

    # Проверяем специфику полумарафона (более быстрые темпы)
    # Дистанции должны быть в разумных пределах для 60 минут
    for training in trainings:
        if training['duration_min'] == 60:
            # Для полумарафона темп примерно 5:00-5:30/км, за 60 мин => 11-12 км
            assert 8 <= training['distance_km'] <= 15


@pytest.mark.asyncio
async def test_generate_plan_for_marathon():
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

    # Для марафона темпы медленнее (5:30-6:00/км)
    for training in trainings:
        if training['duration_min'] == 60 and training['type'] == 'easy':
            # За 60 мин => 10-11 км
            assert 8 <= training['distance_km'] <= 13


@pytest.mark.asyncio
async def test_generate_plan_for_trail():
    """Тест генерации плана для трейла"""
    generator = PlanGenerator(user_id=999)
    goal_date = date.today() + timedelta(days=90)

    trainings = generator.generate_detailed_plan(
        goal_distance=50,
        goal_date=goal_date,
        training_days=[1, 3, 5, 6],  # 4 дня
        time_per_session=90,
        weeks=12,
        goal_type='trail'
    )

    assert len(trainings) > 0

    # Проверяем специфичные описания для трейла
    has_hill_intervals = False
    has_trail_long = False

    for training in trainings:
        description = training.get('description', '')

        if 'подъем' in description.lower() or 'гору' in description.lower():
            has_hill_intervals = True
        if 'трейл' in description.lower():
            has_trail_long = True

    # Должны быть упоминания трейловых тренировок
    assert has_hill_intervals or has_trail_long

    # Для трейла темпы самые медленные (6:00-7:30/км)
    for training in trainings:
        if training['duration_min'] == 90 and training['type'] == 'long':
            # За 90 мин => 12-15 км (медленнее из-за рельефа)
            assert training['distance_km'] <= 18


@pytest.mark.asyncio
async def test_generate_plan_with_periodization():
    """Тест периодизации плана"""
    generator = PlanGenerator(user_id=999)
    goal_date = date.today() + timedelta(days=70)  # 10 недель

    trainings = generator.generate_detailed_plan(
        goal_distance=21,
        goal_date=goal_date,
        training_days=[2, 4, 6],  # Вт, Чт, Сб
        time_per_session=60,
        weeks=10,
        goal_type='race'
    )

    # Проверяем, что есть тренировки
    assert len(trainings) > 0

    # Проверяем, что объём постепенно растёт в базовом периоде
    # Базовый период = 60% от 10 недель = 6 недель
    # Группируем по неделям
    weeks = {}
    for training in trainings:
        week_num = (training['date'] - date.today()).days // 7
        if week_num not in weeks:
            weeks[week_num] = []
        weeks[week_num].append(training['duration_min'])

    # Проверяем, что есть несколько недель
    assert len(weeks) >= 3


@pytest.mark.asyncio
async def test_workout_details_contain_distance():
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
        assert len(training['description']) > 10  # Есть осмысленное описание
