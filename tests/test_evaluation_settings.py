import random

import pytest

from app.config.evaluation_config import EvaluationConfig
from app.services.evaluation_service import EvaluationService, evaluation_repository


def test_should_evaluate_global_switch_wins_over_user_override():
    config = EvaluationConfig(enabled=False, sample_rate=1.0)

    assert config.should_evaluate(enabled=True, sample_rate=1.0) is False


def test_should_evaluate_user_can_disable_or_set_zero_rate():
    config = EvaluationConfig(enabled=True, sample_rate=1.0)

    assert config.should_evaluate(enabled=False, sample_rate=1.0) is False
    assert config.should_evaluate(enabled=True, sample_rate=0.0) is False
    assert config.should_evaluate(enabled=True, sample_rate=1.0) is True


def test_should_evaluate_fractional_rate_uses_random_sampling(monkeypatch):
    config = EvaluationConfig(enabled=True, sample_rate=0.5)

    monkeypatch.setattr(random, "random", lambda: 0.25)
    assert config.should_evaluate(sample_rate=0.5) is True

    monkeypatch.setattr(random, "random", lambda: 0.75)
    assert config.should_evaluate(sample_rate=0.5) is False


def test_user_settings_response_does_not_mutate_global_config():
    config = EvaluationConfig(enabled=True, sample_rate=0.4, async_mode=False)
    service = object.__new__(EvaluationService)
    service.config = config

    response = service._build_user_settings_response(
        {"enabled": True, "sample_rate": 0.7}
    )

    assert response["enabled"] is True
    assert response["sample_rate"] == 0.7
    assert response["user_enabled"] is True
    assert response["user_sample_rate"] == 0.7
    assert response["configured_enabled"] is True
    assert response["configured_sample_rate"] == 0.4
    assert response["is_custom"] is True
    assert response["async_mode"] is False

    assert config.enabled is True
    assert config.sample_rate == 0.4
    assert config.async_mode is False


@pytest.mark.asyncio
async def test_schedule_evaluation_skips_when_saved_user_setting_is_disabled(monkeypatch):
    config = EvaluationConfig(enabled=True, sample_rate=1.0, async_mode=True)
    service = object.__new__(EvaluationService)
    service.config = config

    created = []

    async def fake_get_user_settings(user_id):
        return {"enabled": False, "sample_rate": 1.0}

    async def fake_create(**kwargs):
        created.append(kwargs)

    monkeypatch.setattr(
        evaluation_repository, "get_user_settings", fake_get_user_settings
    )
    monkeypatch.setattr(evaluation_repository, "create", fake_create)

    await service.schedule_evaluation(
        message_id="message-id",
        conversation_id="conversation-id",
        query="query",
        context="context",
        response="response",
        user_id="user-id",
    )

    assert created == []
