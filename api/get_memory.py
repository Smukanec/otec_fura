import json
from pathlib import Path
from datetime import datetime

MEMORY_DIR = Path(__file__).resolve().parent.parent / "memory"

def _ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def _load_jsonl(file_path: Path) -> list[dict]:
    if not file_path.exists():
        return []
    with file_path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

def _append_jsonl(file_path: Path, obj: dict):
    _ensure_dir(file_path.parent)
    with file_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def load_memory_context(user: str, query: str) -> list[str]:
    """Vrátí texty z veřejné i soukromé paměti, které obsahují query (case-insensitive)."""
    q = (query or "").lower()
    results: list[str] = []

    public_file = MEMORY_DIR / "public.jsonl"
    results += [it["text"] for it in _load_jsonl(public_file) if q in it.get("text", "").lower()]

    user_file = MEMORY_DIR / user / "private.jsonl"
    results += [it["text"] for it in _load_jsonl(user_file) if q in it.get("text", "").lower()]

    return results

def append_to_memory(user: str, text: str):
    """Zapíše text do soukromé paměti daného uživatele (jsonl)."""
    user_file = MEMORY_DIR / user / "private.jsonl"
    entry = {
        "text": text,
        "ts": datetime.utcnow().isoformat()
    }
    _append_jsonl(user_file, entry)
