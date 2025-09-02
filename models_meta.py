"""Model metadata hints for Jarvik.

Run this module to regenerate ``static/models_meta.json``:

``python -m models_meta``
"""

from __future__ import annotations

from pathlib import Path
import json
from typing import Dict

# Descriptive hints for models available to the system. The structure mirrors
# the front-end JSON so both sides stay in sync.
MODELS_HINTS: Dict[str, Dict[str, str]] = {
    "command-r": {
        "label": "Command R",
        "tip": "Cohere's reasoning model",
        "description": "Cohere's Command R reasoning model",
        "group": "reasoning",
        "tier": "premium",
        "difficulty": "medium",
        "type": "general",
    },
    "codellama-7b": {
        "label": "CodeLlama 7B",
        "tip": "Meta's code model",
        "description": "Meta's CodeLlama 7B model",
        "group": "code",
        "tier": "standard",
        "difficulty": "medium",
        "type": "code",
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


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Dump MODELS_HINTS to a JSON file"
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=Path(__file__).parent / "static" / "models_meta.json",
        help="Destination JSON file",
    )
    args = parser.parse_args()
    dump_models_meta(args.path)
