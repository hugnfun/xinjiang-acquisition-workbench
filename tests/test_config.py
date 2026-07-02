import os
import importlib
from sidecar import config

def test_text_config_defaults(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("TEXT_MODEL", raising=False)
    monkeypatch.delenv("TEXT_API_BASE", raising=False)
    importlib.reload(config)
    assert config.TEXT_MODEL == "deepseek-v4-pro"
    assert config.TEXT_API_BASE == "https://api.deepseek.com/v1"
    assert config.TEXT_API_KEY == ""

def test_text_config_from_env(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("TEXT_MODEL", "custom-model")
    importlib.reload(config)
    assert config.TEXT_API_KEY == "sk-test"
    assert config.TEXT_MODEL == "custom-model"

def test_vision_config_defaults(monkeypatch):
    monkeypatch.delenv("VISION_API_KEY", raising=False)
    importlib.reload(config)
    assert config.VISION_MODEL == "qwen3-vl:8b"
    assert config.VISION_API_BASE == "http://localhost:11434/v1"
    assert config.VISION_API_KEY == "ollama"
    assert config.VISION_TRIGGER_CONFIDENCE == 0.6
    assert config.VISION_MAX_IMAGES == 1

def test_openai_importable():
    import openai
    assert openai.__version__

def test_task_config_defaults(monkeypatch):
    import importlib
    monkeypatch.delenv("TASK_API_KEY", raising=False)
    monkeypatch.delenv("TASK_MODEL", raising=False)
    monkeypatch.delenv("TASK_API_BASE", raising=False)
    importlib.reload(config)
    assert config.TASK_MODEL == "qwen3.6:27b-q4_K_M"
    assert config.TASK_API_BASE == "http://localhost:11434/v1"
    assert config.TASK_API_KEY == "ollama"

def test_embedding_config_defaults(monkeypatch):
    import importlib
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    importlib.reload(config)
    assert config.EMBEDDING_MODEL == "qwen3-embedding:latest"
    assert config.EMBEDDING_API_BASE == "http://localhost:11434/v1"
    assert config.EMBEDDING_API_KEY == "ollama"

def test_cluster_threshold_default(monkeypatch):
    import importlib
    monkeypatch.delenv("CLUSTER_SIMILARITY_THRESHOLD", raising=False)
    importlib.reload(config)
    assert config.CLUSTER_SIMILARITY_THRESHOLD == 0.78

def test_numpy_importable():
    import numpy
    assert numpy.__version__
