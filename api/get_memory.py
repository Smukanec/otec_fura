# api/get_memory.py
import json
from pathlib import Path
from datetime import datetime

MEMORY_DIR = Path(__file__).resolve().parent.parent / "memory"

def _load_jsonl(file_path: Path) -> list[dict]:
    if not file_path.exists():
        return []
    with file_path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

def load_memory_context(user: str, query: str) -> list[str]:
    """
    Vrátí jen ty řádky z paměti, které obsahují řetězec `query` (case-insensitive).
    Proto když hledáš něco, co v paměti ještě není, seznam bude prázdný – to je v pořádku.
    """
    q = (query or "").lower()
    results: list[str] = []

    public_file = MEMORY_DIR / "public.jsonl"
    results += [item.get("text", "") for item in _load_jsonl(public_file) if q in item.get("text", "").lower()]

    user_file = MEMORY_DIR / user / "private.jsonl"
    results += [item.get("text", "") for item in _load_jsonl(user_file) if q in item.get("text", "").lower()]
    return results

def append_to_memory(user: str, text: str) -> None:
    """
    Přidá nový řádek do osobní paměti uživatele.
    Signatura je DŮLEŽITÁ: append_to_memory(user, text)
    """
    user_dir = MEMORY_DIR / user
    user_dir.mkdir(parents=True, exist_ok=True)
    private_file = user_dir / "private.jsonl"

    record = {
        "text": text,
        "timestamp": datetime.utcnow().isoformat()
    }
    with private_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
