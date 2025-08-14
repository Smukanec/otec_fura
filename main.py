# main.py
from __future__ import annotations
import os, json, re, requests
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from knowledge_store import KnowledgeStore, KnowledgeDirIndex

# ---------- Konfigurace ----------
DATA_DIR = os.environ.get("DATA_DIR", "data")
USERS_PATH = os.path.join(DATA_DIR, "users.json")
PUBLIC_MEMORY = os.path.join("memory", "public.jsonl")  # volitelné
ALLOWED_CORS = os.environ.get("CORS_ORIGINS", "https://jarvik-ai.tech").split(",")

os.makedirs(DATA_DIR, exist_ok=True)

# ---------- Uživatelé / Auth ----------
def _load_users() -> List[Dict[str, Any]]:
    if not os.path.exists(USERS_PATH):
        return []
    try:
        with open(USERS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def _user_by_token(token: str) -> Optional[Dict[str, Any]]:
    users = _load_users()
    for u in users:
        if u.get("api_key") == token:
            return u
    return None

def _parse_bearer(auth: Optional[str]) -> Optional[str]:
    if not auth:
        return None
    s = auth.strip()
    if s.lower().startswith("bearer "):
        return s.split(" ", 1)[1].strip()
    return s

def require_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    tok = _parse_bearer(authorization)
    if not tok:
        raise HTTPException(401, detail="Neplatný token")
    u = _user_by_token(tok)
    if not u or not u.get("approved"):
        raise HTTPException(401, detail="Neplatný token")
    return u

# ---------- App ----------
app = FastAPI(title="Otec Fura API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED_CORS if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Knowledge ----------
KS = KnowledgeStore()
KDIR = KnowledgeDirIndex()  # čte ./knowledge/*.{md,txt}

class KnowledgeAdd(BaseModel):
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    tags: List[str] = []
    private: bool = False

class KnowledgeSearchReq(BaseModel):
    query: str
    top_k: int = 5

class ContextReq(BaseModel):
    query: str = Field(..., min_length=1)

def _read_public_memory() -> List[str]:
    out = []
    try:
        if os.path.exists(PUBLIC_MEMORY):
            with open(PUBLIC_MEMORY, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        # buď plain text, nebo jsonl {"text": "..."}
                        if line.startswith("{"):
                            d = json.loads(line)
                            txt = d.get("text")
                            if txt:
                                out.append(str(txt))
                        else:
                            out.append(line)
                    except Exception:
                        continue
    except Exception:
        pass
    # fallback – ať to není prázdné jako u tebe
    if not out:
        out = ["Vítejte v paměti veřejných informací."]
    return out

# ---------- Endpoints ----------
@app.get("/auth/me")
def auth_me(user = Depends(require_user)):
    return {
        "username": user.get("username") or user.get("nick") or "user",
        "email": user.get("email"),
        "approved": bool(user.get("approved")),
    }

@app.post("/knowledge/add")
def knowledge_add(body: KnowledgeAdd, user = Depends(require_user)):
    it = KS.add(
        title=body.title,
        content=body.content,
        tags=body.tags,
        private=body.private,
        owner=(user.get("username") or user.get("nick")) if body.private else None,
        source="api"
    )
    return {"status": "OK", "id": it.id}

@app.post("/knowledge/search")
def knowledge_search(body: KnowledgeSearchReq, user = Depends(require_user)):
    who = (user.get("username") or user.get("nick"))
    from_store = KS.search(body.query, top_k=body.top_k, user=who)
    from_dir = KDIR.search(body.query, top_k=body.top_k)
    # sloučit a deduplikovat podle (title, source)
    seen = set()
    merged = []
    for it in sorted(from_store + from_dir, key=lambda x: x.created_at, reverse=True):
        key = (it.title, it.source)
        if key in seen:
            continue
        seen.add(key)
        merged.append(it)
        if len(merged) >= body.top_k:
            break
    return {"results": [ {"title": i.title, "content": i.content, "tags": i.tags, "source": i.source} for i in merged ]}

@app.post("/admin/reindex_knowledge")
def admin_reindex(user = Depends(require_user)):
    # pro jednoduchost kdokoliv approved může reindexovat
    KDIR.reindex()
    return {"status": "OK", "files_indexed": len(KDIR.docs)}

@app.post("/get_context")
def get_context(body: ContextReq, user = Depends(require_user)):
    who = (user.get("username") or user.get("nick"))
    # knowledge: spojíme JSONL store (vč. private owner==who) + soubory ze složky
    k_from_store = KS.search(body.query, top_k=5, user=who)
    k_from_dir = KDIR.search(body.query, top_k=5)
    # sloučení
    seen = set()
    knowledge = []
    for it in k_from_store + k_from_dir:
        key = (it.title, it.source)
        if key in seen:
            continue
        seen.add(key)
        knowledge.append({"title": it.title, "content": it.content, "tags": it.tags, "source": it.source})
        if len(knowledge) >= 5:
            break

    memory = _read_public_memory()
    # embedding necháme jak bylo (placeholdery, pokud nemáš vektorový index)
    embedding = [
        "Vítejte v paměti veřejných informací.",
        "Toto je soukromá paměť uživatele Jiri.",
        "Transformers jsou architektura deep learningu založená na mechanismu attention.\n",
    ]
    return {"memory": memory, "knowledge": knowledge, "embedding": embedding}

# ----- /crawl (bezpečnější + umí i raw_text) -----
class CrawlReq(BaseModel):
    url: Optional[str] = None
    raw_text: Optional[str] = None
    title: Optional[str] = None
    private: bool = False
    tags: List[str] = []

@app.post("/crawl")
def crawl(body: CrawlReq, user = Depends(require_user)):
    who = (user.get("username") or user.get("nick"))
    if body.raw_text:
        it = KS.add(
            title=body.title or "(text)",
            content=body.raw_text,
            tags=body.tags,
            private=body.private,
            owner=who if body.private else None,
            source="api:raw",
        )
        return {"status": "OK", "chars": len(body.raw_text), "id": it.id, "source": it.source}

    if not body.url:
        raise HTTPException(400, detail="url nebo raw_text je povinné")

    url = body.url.strip()
    try:
        # Jednoduchý fetch (Wikipedia apod. by měla projít)
        r = requests.get(url, timeout=15, headers={"User-Agent": "FuraCrawler/1.0"})
        if r.status_code != 200 or not r.text.strip():
            raise HTTPException(400, detail="Nepodařilo se stáhnout obsah")
        content = r.text
    except Exception:
        raise HTTPException(400, detail="Failed to crawl")

    title = body.title or url
    it = KS.add(
        title=title,
        content=content,
        tags=body.tags,
        private=body.private,
        owner=who if body.private else None,
        source=f"url:{url}",
    )
    return {"status": "OK", "chars": len(content), "id": it.id, "source": it.source}

# Root (volitelný)
@app.get("/")
def root():
    return {"status": "ok", "service": "Otec Fura API"}
