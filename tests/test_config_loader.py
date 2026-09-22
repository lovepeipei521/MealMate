from app.config import config_loader


def test_load_llm_config_uses_top_level_vision_model(monkeypatch):
    monkeypatch.setattr(
        config_loader,
        "_load_config_data",
        lambda: {
            "llm": {
                "vision": {
                    "model_names": ["legacy-vision-model"],
                    "base_url": "https://legacy.example/v1",
                }
            },
            "vision": {
                "model": {
                    "enabled": False,
                    "model_name": "top-level-vision-model",
                    "base_url": "https://vision.example/v1",
                    "temperature": 0.2,
                    "max_tokens": 2048,
                    "max_image_size_mb": 8.0,
                    "request_timeout": 90,
                }
            },
        },
    )
    monkeypatch.setenv("LLM_API_KEY", "test-llm-key")
    monkeypatch.delenv("VISION_API_KEY", raising=False)

    config = config_loader.load_llm_config()

    assert config.vision.enabled is False
    assert config.vision.model_names == ["top-level-vision-model"]
    assert config.vision.base_url == "https://vision.example/v1"
    assert config.vision.temperature == 0.2
    assert config.vision.max_tokens == 2048
    assert config.vision.max_image_size_mb == 8.0
    assert config.vision.request_timeout == 90
    assert config.vision.api_key == "test-llm-key"


def test_load_llm_config_keeps_llm_vision_fallback(monkeypatch):
    monkeypatch.setattr(
        config_loader,
        "_load_config_data",
        lambda: {
            "llm": {
                "vision": {
                    "model_names": ["fallback-vision-model"],
                    "base_url": "https://fallback.example/v1",
                }
            }
        },
    )
    monkeypatch.delenv("VISION_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    config = config_loader.load_llm_config()

    assert config.vision.model_names == ["fallback-vision-model"]
    assert config.vision.base_url == "https://fallback.example/v1"