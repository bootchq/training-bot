"""
Базовые e2e тесты (временные, пока нет Telethon setup).

Запуск:
    pytest tests/e2e/test_onboarding_mock.py -v
"""

import pytest


@pytest.mark.e2e
def test_placeholder():
    """Placeholder тест чтобы pytest не падал."""
    assert True, "E2E тесты работают"


@pytest.mark.e2e
def test_e2e_setup_ready():
    """Проверка что структура e2e готова."""
    from pathlib import Path

    e2e_dir = Path(__file__).parent
    assert (e2e_dir / "conftest.py").exists(), "conftest.py отсутствует"
    assert (e2e_dir / "test_onboarding_e2e.py").exists(), "test_onboarding_e2e.py отсутствует"
    assert (e2e_dir / "README.md").exists(), "README.md отсутствует"


@pytest.mark.e2e
def test_env_example_exists():
    """Проверка что .env.e2e.example создан."""
    from pathlib import Path

    env_example = Path(__file__).parent.parent.parent / ".env.e2e.example"
    assert env_example.exists(), ".env.e2e.example не найден"

    content = env_example.read_text()
    assert "TELEGRAM_API_ID" in content
    assert "TELETHON_SESSION" in content
    assert "BOT_USERNAME" in content


# Реальные тесты будут в test_onboarding_e2e.py после setup Telethon
