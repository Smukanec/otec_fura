# api/get_memory.py
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime
from typing import List

MEMORY_DIR = Path(__file__).resolve().parent.parent / "memory"

def _load_jsonl(file_path: Path) -> list[dict]:
    if not file_path.exists():
        return []
    with file_path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

def _append_jsonl(file_path: Path, obj: dict) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def load_memory_context(user: str, query: str) -> List[str]:
    """Vrátí relevantní řádky z public + private, které obsahují dotaz (case-insensitive)."""
    q = (query or "").lower()
    out: List[str] = []

    public_file = MEMORY_DIR / "public.jsonl"
    out += [item.get("text", "")
            for item in _load_jsonl(public_file)
            if q in item.get("text", "").lower()]

    user_file = MEMORY_DIR / user / "private.jsonl"
    out += [item.get("text", "")
            for item in _load_jsonl(user_file)
            if q in item.get("text", "").lower()]

    return out

def append_to_memory(user: str, text: str) -> None:
    """Zapíše do privátní paměti daného uživatele jednoduchý záznam."""
    user_file = MEMORY_DIR / user / "private.jsonl"
    _append_jsonl(user_file, {
        "ts": datetime.utcnow().isoformat() + "Z",
        "text": text
    })
