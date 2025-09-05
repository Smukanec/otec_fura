import json
from pathlib import Path

from models_meta import MODELS_HINTS, ALLOWED_MODELS, dump_models_meta


def test_allowed_models():
    assert "command-r" in ALLOWED_MODELS
    assert "codellama-7b" in ALLOWED_MODELS
    assert "llama3:8b" in ALLOWED_MODELS
    assert "mistral:7b" in ALLOWED_MODELS
    assert "mixtral:8x7b" in ALLOWED_MODELS
    assert "starcoder:7b" in ALLOWED_MODELS
    assert "nous-hermes2:latest" in ALLOWED_MODELS
    assert "gpt-oss:latest" in ALLOWED_MODELS
    assert "gpt4" not in ALLOWED_MODELS
    assert "llama2" not in ALLOWED_MODELS


def test_dump_models_meta(tmp_path: Path):
    target = tmp_path / "models_meta.json"
    dump_models_meta(target)
    data = json.loads(target.read_text("utf-8"))
    assert data == MODELS_HINTS
