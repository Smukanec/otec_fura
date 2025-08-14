import os
import json
import time
import logging
from typing import Optional, List, Dict

import requests
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from knowledge_store import KnowledgeStore

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(APP_DIR, "data")
USERS_PATH = os.path.join(DATA_DIR, "users.json")
MEMORY_DIR = os.path.join(APP_DIR, "memory")
KNOWLEDGE_DIR = os.path.join(APP_DIR, "knowledge")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MEMORY_DIR, exist_ok=True)
os.makedirs(KNOWLEDGE_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
LOGGER = logging.getLogger("fura")

# ---- CORS ----
ALLOW_ORIGINS = [
    "https://jarvik-ai.tech",
    "https://www.jarvik-ai.tech",
    "http://localhost:8010",
    "http://127.0.0.1:8010",
]
app = FastAPI(title="Otec Fura API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS if os.getenv("STRICT_CORS", "1") == "1" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Knowledge store ----
STORE = KnowledgeStore(APP_DIR)
STORE.load()


# -------- Models --------
class QueryIn(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(5, ge=1, le=20)


class AddKnowledgeIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    content: str = Field(..., min_length=1)
    tags: Optional[List[str]] = None


class CrawlIn(BaseModel):
    url: Optional[str] = None
    raw_text: Optional[str] = None
    title: Optional[str] = None
    tags: Optional[List[str]] = None


# -------- Auth helpers --------
def _load_users() -> List[Dict]:
    if not os.path.exists(USERS_PATH):
        return []
    with open(USERS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return list(data.values())
    return data


def _validate_token(authorization: Optional[str]) -> Dict:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing token")

    token = authorization
    if token.lower().startswith("bearer "):
        token = token.split(" ", 1)[1].strip()

    users = _load_users()
    for u in users:
        if str(u.get("api_key", "")).strip() == token:
            if not u.get("approved", False):
                raise HTTPException(status_code=403, detail="account not approved")
            # normalize output
            return {
                "username": u.get("username") or u.get("nick") or "user",
                "email": u.get("email") or "",
                "approved": True,
                "api_key": token,
            }

    raise HTTPException(status_code=401, detail="Neplatný token")


# -------- Memory helpers --------
def _read_jsonl(path: str) -> List[str]:
    out = []
    if not os.path.exists(path):
        return out
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict) and "text" in obj:
                    out.append(str(obj["text"]))
                else:
                    out.append(line)
            except Exception:
                out.append(line)
    return out


def _get_public_memory() -> List[str]:
    pub_path = os.path.join(MEMORY_DIR, "public.jsonl")
    return _read_jsonl(pub_path)


# -------- Routes --------
@app.get("/health")
def health():
    return {"ok": True, "time": int(time.time())}


@app.get("/auth/me")
def auth_me(Authorization: Optional[str] = Header(default=None)):
    user = _validate_token(Authorization)
    return {"username": user["username"], "email": user["email"], "approved": True}


@app.post("/knowledge/add")
def knowledge_add(payload: AddKnowledgeIn, Authorization: Optional[str] = Header(default=None)):
    _validate_token(Authorization)
    res = STORE.add_document(
        title=payload.title,
        content=payload.content,
        source="manual",
        tags=payload.tags or [],
    )
    return res


@app.post("/admin/reindex_knowledge")
def admin_reindex(Authorization: Optional[str] = Header(default=None)):
    _validate_token(Authorization)
    res = STORE.reindex_folder(KNOWLEDGE_DIR)
    return res


@app.post("/knowledge/search")
def knowledge_search(q: QueryIn, Authorization: Optional[str] = Header(default=None)):
    _validate_token(Authorization)
    results = STORE.search(q.query, top_k=q.top_k)
    return {"results": results}


@app.post("/get_context")
def get_context(q: QueryIn, Authorization: Optional[str] = Header(default=None)):
    _validate_token(Authorization)
    memory = _get_public_memory()
    knowledge = STORE.search(q.query, top_k=q.top_k)
    # For compatibility with your UI expectations:
    embedding = [
        "Vítejte v paměti veřejných informací.",
        "Toto je soukromá paměť uživatele Jiri.",
        "Transformers jsou architektura deep learningu založená na mechanismu attention.\n",
    ]
    return {
        "memory": memory,
        "knowledge": knowledge,
        "embedding": embedding,
    }


# ---------- Crawl ----------
def _fetch_url_text(url: str) -> Dict:
    """Return {'title','content','source'} from URL (HTML or PDF)."""
    ua = "Jarvik-FuraCrawler/1.0 (+https://jarvik-ai.tech)"
    try:
        r = requests.get(url, headers={"User-Agent": ua}, timeout=15, allow_redirects=True, stream=True)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fetch failed: {e}")

    ct = r.headers.get("Content-Type", "")
    # PDF?
    if "application/pdf" in ct or url.lower().endswith(".pdf"):
        # read binary into temp buffer
        data = r.content
        tmp = os.path.join(KNOWLEDGE_DIR, f"fura_tmp_{int(time.time()*1000)}.pdf")
        with open(tmp, "wb") as f:
            f.write(data)
        try:
            from knowledge_store import _extract_text_from_pdf  # reuse
            text = _extract_text_from_pdf(tmp)
        finally:
            try:
                os.remove(tmp)
            except Exception:
                pass
        if not text.strip():
            raise HTTPException(status_code=400, detail="Empty PDF text after parsing")
        title = os.path.basename(url).split("?")[0]
        return {"title": title, "content": text, "source": url}

    # HTML
    text = r.text or ""
    soup = None
    try:
        soup = BeautifulSoup(text, "html.parser")
        # remove script/style/nav/footer
        for bad in soup(["script", "style", "nav", "footer", "noscript"]):
            bad.decompose()
        title = (soup.title.string if soup.title else url) or url
        body = soup.get_text(" ", strip=True)
    except Exception:
        title = url
        body = text
    if not body.strip():
        raise HTTPException(status_code=400, detail="Empty HTML after cleaning")

    return {"title": title[:200], "content": body, "source": url}


@app.post("/crawl")
def crawl(payload: CrawlIn, Authorization: Optional[str] = Header(default=None)):
    _validate_token(Authorization)

    if payload.raw_text:
        title = payload.title or "Raw text note"
        res = STORE.add_document(title=title, content=payload.raw_text, source="raw_text", tags=payload.tags or [])
        return {"ok": True, "mode": "raw_text", **res}

    if payload.url:
        data = _fetch_url_text(payload.url)
        res = STORE.add_document(
            title=payload.title or data["title"],
            content=data["content"],
            source=data["source"],
            tags=(payload.tags or []) + ["crawl"],
        )
        return {"ok": True, "mode": "url", **res}

    raise HTTPException(status_code=400, detail="Provide either 'url' or 'raw_text'")


# Root for quick sanity
@app.get("/")
def root():
    return {"service": "fura", "knowledge_items": len(STORE._items)}
