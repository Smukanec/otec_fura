# api/get_memory.py
import json
from pathlib import Path
from typing import List

# /.../otec_fura/api/get_memory.py  →  PROJECT_ROOT = .../otec_fura
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEMORY_DIR = PROJECT_ROOT / "memory"

def _load_jsonl(file_path: Path) -> List[dict]:
    if not file_path.exists():
        return []
    with file_path.open("r", encoding="utf-8") as f:
        lines = []
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                lines.append(json.loads(line))
            except Exception:
                # poškozená řádka? přeskoč
                continue
        return lines

def load_memory_context(user: str, query: str) -> List[str]:
    """Vrátí relevantní řádky z public a user paměti, které obsahují query (case-insensitive)."""
    q = (query or "").lower()
    out: List[str] = []

    public_file = MEMORY_DIR / "public.jsonl"
    out += [it.get("text", "") for it in _load_jsonl(public_file) if q in it.get("text", "").lower()]

    user_file = MEMORY_DIR / user / "private.jsonl"
    out += [it.get("text", "") for it in _load_jsonl(user_file) if q in it.get("text", "").lower()]

    return out

def append_to_memory(user: str, text: str, note: str | None = None) -> None:
    """
    Přidá řádku do user paměti (JSONL). Vytvoří složku/soubor pokud chybí.
    Zapisuje jako {"text": "..."}; pokud je note, připojí ji na konec.
    """
    user = user.strip() or "anonymous"
    target_dir = MEMORY_DIR / user
    target_dir.mkdir(parents=True, exist_ok=True)

    target_file = target_dir / "private.jsonl"
    payload = {"text": text if not note else f"{text} - {note}"}

    with target_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
