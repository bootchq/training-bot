"""Тест AI Recovery Detector"""
import sys
from pathlib import Path

# Добавляем корневую папку в sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ai.recovery_detector import recovery_detector
from src.utils.logger import logger


def test_recovery_detection(user_id: int = 57186925):
    """Тест детекции восстановления"""
    logger.info(f"🧪 Тестирую AI Recovery Detector для user_id={user_id}")

    try:
        result = recovery_detector.detect_recovery_status(user_id)

        print("\n" + "="*60)
        print("🔋 СТАТУС ВОССТАНОВЛЕНИЯ")
        print("="*60)
        print(f"Статус:      {result['status_text']} ({result['status']})")
        print(f"Уверенность: {result['confidence']*100:.0f}%")
        print(f"\nОбоснование:")
        print(f"  {result['reasoning']}")

        if result['metrics']:
            print(f"\nМетрики:")
            for key, value in result['metrics'].items():
                if value is not None:
                    print(f"  {key}: {value}")

        print("="*60)

        logger.info("✅ Тест успешен!")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка теста: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_recovery_detection()
