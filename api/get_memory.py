# api/get_memory.py
import json
from pathlib import Path

MEMORY_DIR = Path(__file__).resolve().parent.parent / "memory"

def _load_jsonl(file_path: Path) -> list[dict]:
    if not file_path.exists():
        return []
    with file_path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

def load_memory_context(user: str, query: str) -> list[str]:
    results: list[str] = []
    public_file = MEMORY_DIR / "public.jsonl"
    results += [i["text"] for i in _load_jsonl(public_file) if query.lower() in i.get("text", "").lower()]
    user_file = MEMORY_DIR / user / "private.jsonl"
    results += [i["text"] for i in _load_jsonl(user_file) if query.lower() in i.get("text", "").lower()]
    return results

def append_to_memory(user: str, text: str) -> None:
    user_dir = MEMORY_DIR / user
    user_dir.mkdir(parents=True, exist_ok=True)
    user_file = user_dir / "private.jsonl"
    with user_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"text": text}, ensure_ascii=False) + "\n")
