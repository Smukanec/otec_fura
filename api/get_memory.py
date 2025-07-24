import json
from pathlib import Path
from typing import List

MEMORY_DIR = Path(__file__).resolve().parent.parent / "memory"


def _load_jsonl(file_path: Path) -> List[dict]:
    if not file_path.exists():
        return []
    with file_path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_memory_context(user: str, query: str) -> List[str]:
    """Načte relevantní paměť pro daného uživatele."""
    results = []
    public_file = MEMORY_DIR / "public.jsonl"
    results += [item["text"] for item in _load_jsonl(public_file) if query.lower() in item.get("text", "").lower()]

    user_file = MEMORY_DIR / user / "private.jsonl"
    results += [item["text"] for item in _load_jsonl(user_file) if query.lower() in item.get("text", "").lower()]
    return results
