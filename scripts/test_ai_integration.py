"""Комплексный тест всех AI модулей Phase 3"""
import sys
from pathlib import Path

# Добавляем корневую папку в sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ai.workout_recommender import workout_recommender
from src.ai.recovery_detector import recovery_detector
from src.ai.weekly_coach import weekly_coach
from src.utils.logger import logger


def test_all_ai_modules(user_id: int = 57186925):
    """Комплексный тест всех AI модулей"""
    logger.info(f"🧪 Тестирую все AI модули Phase 3 для user_id={user_id}")

    print("\n" + "="*70)
    print(" "*20 + "🤖 AI INTEGRATION TEST")
    print("="*70)

    success_count = 0
    total_tests = 3

    # ========== TEST 1: Workout Recommender ==========
    print("\n" + "─"*70)
    print("TEST 1/3: AI Workout Recommendations")
    print("─"*70)
    try:
        recommendation = workout_recommender.get_recommendation(user_id)
        print(f"✅ Тип: {recommendation['workout_type']}")
        print(f"   Длительность: {recommendation['duration_min']} мин")
        print(f"   Дистанция: {recommendation['distance_km']} км")
        print(f"   Зона: {recommendation['target_zone']}")
        print(f"   Обоснование: {recommendation['reasoning'][:80]}...")
        success_count += 1
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        logger.error(f"Workout Recommender failed: {e}")

    # ========== TEST 2: Recovery Detector ==========
    print("\n" + "─"*70)
    print("TEST 2/3: Smart Recovery Detection")
    print("─"*70)
    try:
        recovery = recovery_detector.detect_recovery_status(user_id)
        print(f"✅ Статус: {recovery['status_text']} ({recovery['status']})")
        print(f"   Уверенность: {recovery['confidence']*100:.0f}%")
        print(f"   Обоснование: {recovery['reasoning'][:80]}...")
        success_count += 1
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        logger.error(f"Recovery Detector failed: {e}")

    # ========== TEST 3: Weekly Coach ==========
    print("\n" + "─"*70)
    print("TEST 3/3: Coaching Insights")
    print("─"*70)
    try:
        insights = weekly_coach.get_weekly_insights(user_id)
        print(f"✅ Сводка: {insights['summary'][:80]}...")
        print(f"   Выполнено тренировок: {insights['plan_vs_actual']['actual_workouts']}/{insights['plan_vs_actual']['planned_workouts']}")
        print(f"   Инсайтов: {len(insights['insights'])}")
        print(f"   Рекомендаций: {len(insights['recommendations'])}")
        success_count += 1
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        logger.error(f"Weekly Coach failed: {e}")

    # ========== SUMMARY ==========
    print("\n" + "="*70)
    print(f" "*25 + "📊 ИТОГИ ТЕСТИРОВАНИЯ")
    print("="*70)
    print(f"\nУспешно:  {success_count}/{total_tests} модулей")
    print(f"Провалено: {total_tests - success_count}/{total_tests} модулей")

    if success_count == total_tests:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
        print("\nPhase 3 (AI Integration) реализован полностью:")
        print("  ✅ AI Workout Recommendations")
        print("  ✅ Smart Recovery Detection")
        print("  ✅ Coaching Insights")
        logger.info("✅ Все AI модули работают корректно!")
        return True
    else:
        print(f"\n⚠️  ПРОВАЛЕНО {total_tests - success_count} ТЕСТОВ")
        logger.warning(f"Провалено тестов: {total_tests - success_count}")
        return False


if __name__ == "__main__":
    success = test_all_ai_modules()
    sys.exit(0 if success else 1)
