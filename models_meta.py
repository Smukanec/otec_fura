"""Model metadata hints for Jarvik."""

from __future__ import annotations

from pathlib import Path
import json
from typing import Dict

# Descriptive hints for models available to the system. The structure mirrors
# the front-end JSON so both sides stay in sync.
MODELS_HINTS: Dict[str, Dict[str, str]] = {
    "command-r": {
        "label": "Command R",
        "description": "Cohere's Command R reasoning model",
        "difficulty": "medium",
        "type": "general",
    },
    "codellama-7b": {
        "label": "CodeLlama 7B",
        "description": "Meta's CodeLlama 7B model",
        "difficulty": "medium",
        "type": "code",
    },
    "gpt4": {
        "label": "GPT-4",
        "description": "OpenAI GPT-4 model",
        "difficulty": "high",
        "type": "general",
    },
    "llama2": {
        "label": "LLaMA2",
        "description": "Meta's LLaMA2 model",
        "difficulty": "medium",
        "type": "general",
    },
}

# Convenient set of allowed model identifiers
ALLOWED_MODELS = set(MODELS_HINTS.keys())


def dump_models_meta(path: str | Path) -> None:
    """Dump :data:`MODELS_HINTS` to ``path`` as JSON.

    Parameters
    ----------
    path:
        Destination file path. It can be a string or :class:`~pathlib.Path`.
    """

    dest = Path(path)
    dest.write_text(
        json.dumps(MODELS_HINTS, indent=2, ensure_ascii=False), encoding="utf-8"
    )
