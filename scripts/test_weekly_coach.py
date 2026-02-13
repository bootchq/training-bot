"""Тест AI Weekly Coach"""
import sys
from pathlib import Path

# Добавляем корневую папку в sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ai.weekly_coach import weekly_coach
from src.utils.logger import logger


def test_weekly_insights(user_id: int = 57186925):
    """Тест еженедельного анализа"""
    logger.info(f"🧪 Тестирую AI Weekly Coach для user_id={user_id}")

    try:
        insights = weekly_coach.get_weekly_insights(user_id)

        print("\n" + "="*60)
        print("📊 ЕЖЕНЕДЕЛЬНЫЙ АНАЛИЗ")
        print("="*60)

        print(f"\n📝 Сводка:")
        print(f"  {insights['summary']}")

        print(f"\n📈 План vs Факт:")
        pva = insights['plan_vs_actual']
        print(f"  Тренировок: {pva['actual_workouts']}/{pva['planned_workouts']} ({pva['completion_rate']:.0f}%)")
        print(f"  Дистанция: {pva['actual_distance']:.1f}/{pva['planned_distance']:.1f} км")

        if insights['progress_metrics']:
            print(f"\n📊 Метрики прогресса:")
            for key, value in insights['progress_metrics'].items():
                if value is not None:
                    print(f"  {key}: {value}")

        if insights['insights']:
            print(f"\n💡 Инсайты:")
            for i, insight in enumerate(insights['insights'], 1):
                print(f"  {i}. {insight}")

        if insights['recommendations']:
            print(f"\n🎯 Рекомендации:")
            for i, rec in enumerate(insights['recommendations'], 1):
                print(f"  {i}. {rec}")

        print("="*60)

        logger.info("✅ Тест успешен!")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка теста: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_weekly_insights()
