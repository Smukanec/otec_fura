# knowledge_store.py
from __future__ import annotations
import os, re, json, uuid, time, threading
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any, Tuple

# --- Konfigurace přes env ---
JSONL_PATH = os.environ.get("KNOWLEDGE_JSONL", "data/knowledge.jsonl")
KNOWLEDGE_DIR = os.environ.get("KNOWLEDGE_DIR", "knowledge")
SUPPORTED_EXT = {".md", ".txt", ".pdf"}  # PDF podpora
PDF_MAX_PAGES = int(os.environ.get("PDF_MAX_PAGES", "30"))
MAX_FILE_MB = float(os.environ.get("KNOWLEDGE_MAX_FILE_MB", "25"))

def _now_ts() -> float:
    return time.time()

def _read_file_text_generic(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return None

def _read_pdf_text(path: str) -> Optional[str]:
    # 1) PyPDF2
    try:
        from PyPDF2 import PdfReader  # pip install PyPDF2
        reader = PdfReader(path)
        pages = min(len(reader.pages), max(1, PDF_MAX_PAGES))
        out = []
        for i in range(pages):
            try:
                t = reader.pages[i].extract_text() or ""
            except Exception:
                t = ""
            if t.strip():
                out.append(t)
        txt = "\n\n".join(out).strip()
        if txt:
            return txt
    except Exception:
        pass
    # 2) pdfminer.six (fallback)
    try:
        from pdfminer.high_level import extract_text  # pip install pdfminer.six
        txt = extract_text(path)
        return txt.strip() if txt and txt.strip() else None
    except Exception:
        pass
    return None

def _read_text_file(path: str) -> Optional[str]:
    _, ext = os.path.splitext(path.lower())
    try:
        size_mb = os.path.getsize(path) / (1024 * 1024)
        if size_mb > MAX_FILE_MB:
            return None
    except Exception:
        pass
    if ext == ".pdf":
        return _read_pdf_text(path)
    else:
        return _read_file_text_generic(path)

def _first_heading_or_name(path: str, text: str) -> str:
    for line in (text or "").splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            return re.sub(r"^#+\s*", "", s)
        return s[:120]
    return os.path.basename(path)

def _tokenize(s: str) -> List[str]:
    return re.findall(r"[a-zá-ž0-9]+", (s or "").lower())

def _score(query: str, text: str, title: str = "") -> float:
    q = _tokenize(query)
    if not q:
        return 0.0
    tks = _tokenize(text)
    if not tks:
        return 0.0
    freq: Dict[str, int] = {}
    for t in tks:
        freq[t] = freq.get(t, 0) + 1
    score = 0.0
    for qt in q:
        score += freq.get(qt, 0)
    if query.lower() in (text or "").lower():
        score += 3.0
    if title and query.lower() in title.lower():
        score += 2.0
    return score

@dataclass
class KnowledgeItem:
    id: str
    title: str
    content: str
    tags: List[str]
    private: bool
    owner: Optional[str]
    source: str
    created_at: float

    @staticmethod
    def from_json(d: Dict[str, Any]) -> "KnowledgeItem":
        return KnowledgeItem(
            id=d.get("id") or str(uuid.uuid4()),
            title=d.get("title") or "(bez názvu)",
            content=d.get("content") or "",
            tags=list(d.get("tags") or []),
            private=bool(d.get("private") or False),
            owner=d.get("owner"),
            source=d.get("source") or "api",
            created_at=float(d.get("created_at") or _now_ts()),
        )

class KnowledgeStore:
    def __init__(self, jsonl_path: str = JSONL_PATH):
        self.jsonl_path = jsonl_path
        os.makedirs(os.path.dirname(self.jsonl_path), exist_ok=True)
        self._lock = threading.RLock()
        self.items: List[KnowledgeItem] = []
        self._load_jsonl()

    def _load_jsonl(self):
        if not os.path.exists(self.jsonl_path):
            return
        with self._lock:
            self.items.clear()
            with open(self.jsonl_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                        self.items.append(KnowledgeItem.from_json(d))
                    except Exception:
                        continue

    def add(self, title: str, content: str, tags: Optional[List[str]] = None,
            private: bool = False, owner: Optional[str] = None,
            source: str = "api") -> KnowledgeItem:
        it = KnowledgeItem(
            id=str(uuid.uuid4()),
            title=title or "(bez názvu)",
            content=content or "",
            tags=list(tags or []),
            private=bool(private),
            owner=owner,
            source=source,
            created_at=_now_ts(),
        )
        with self._lock:
            with open(self.jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(it), ensure_ascii=False) + "\n")
            self.items.append(it)
        return it

    def search(self, query: str, top_k: int = 5, user: Optional[str] = None) -> List[KnowledgeItem]:
        if not query.strip():
            return []
        scored: List[Tuple[float, KnowledgeItem]] = []
        with self._lock:
            for it in self.items:
                if it.private and it.owner and user and user != it.owner:
                    continue
                s = _score(query, it.content, it.title)
                if s > 0:
                    scored.append((s, it))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [it for _, it in scored[:max(1, top_k)]]

class KnowledgeDirIndex:
    """Rekurzivně indexuje KNOWLEDGE_DIR (md/txt/pdf) do paměti."""
    def __init__(self, root: str = KNOWLEDGE_DIR):
        self.root = root
        self.docs: List[KnowledgeItem] = []
        self.reindex()

    def _acceptable(self, path: str) -> bool:
        _, ext = os.path.splitext(path.lower())
        if ext not in SUPPORTED_EXT:
            return False
        try:
            size_mb = os.path.getsize(path) / (1024 * 1024)
            if size_mb > MAX_FILE_MB:
                return False
        except Exception:
            pass
        return True

    def reindex(self):
        self.docs.clear()
        if not os.path.isdir(self.root):
            return
        for base, _, files in os.walk(self.root):
            for fn in files:
                path = os.path.join(base, fn)
                if not self._acceptable(path):
                    continue
                txt = _read_text_file(path)
                if not txt:
                    continue
                title = _first_heading_or_name(path, txt)
                rel = os.path.relpath(path, self.root)
                self.docs.append(
                    KnowledgeItem(
                        id=str(uuid.uuid4()),
                        title=title,
                        content=txt,
                        tags=[],
                        private=False,
                        owner=None,
                        source=f"file:{rel}",
                        created_at=_now_ts(),
                    )
                )

    def search(self, query: str, top_k: int = 5) -> List[KnowledgeItem]:
        if not query.strip():
            return []
        scored: List[Tuple[float, KnowledgeItem]] = []
        for it in self.docs:
            s = _score(query, it.content, it.title)
            if s > 0:
                scored.append((s, it))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [it for _, it in scored[:max(1, top_k)]]
