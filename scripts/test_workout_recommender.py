"""Тест AI Workout Recommender"""
import sys
from pathlib import Path

# Добавляем корневую папку в sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ai.workout_recommender import workout_recommender
from src.utils.logger import logger


def test_recommendation(user_id: int = 57186925):
    """Тест рекомендации тренировки"""
    logger.info(f"🧪 Тестирую AI Workout Recommender для user_id={user_id}")

    try:
        recommendation = workout_recommender.get_recommendation(user_id)

        print("\n" + "="*60)
        print("📋 AI РЕКОМЕНДАЦИЯ ТРЕНИРОВКИ")
        print("="*60)
        print(f"Тип:        {recommendation['workout_type']}")
        print(f"Длительность: {recommendation['duration_min']} мин")
        print(f"Дистанция:   {recommendation['distance_km']} км")
        print(f"Зона пульса: {recommendation['target_zone']}")
        print(f"\nОписание:")
        print(f"  {recommendation['description']}")
        print(f"\nОбоснование:")
        print(f"  {recommendation['reasoning']}")
        print("="*60)

        logger.info("✅ Тест успешен!")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка теста: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_recommendation()
