# main.py
from __future__ import annotations
import os, json, re, tempfile, time
from typing import Optional, List, Dict, Any

import requests
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from knowledge_store import KnowledgeStore, KnowledgeDirIndex, _read_pdf_text

# ----------------------------
# Konfigurace
# ----------------------------
USERS_PATH = os.environ.get("USERS_PATH", "data/users.json")
KNOWLEDGE_JSONL = os.environ.get("KNOWLEDGE_JSONL", "data/knowledge.jsonl")
KNOWLEDGE_DIR = os.environ.get("KNOWLEDGE_DIR", "knowledge")
CRAWL_TIMEOUT = int(os.environ.get("CRAWL_TIMEOUT", "15"))
USER_AGENT = os.environ.get("CRAWL_UA", "OtecFuraBot/1.0 (+github.com/Smukanec)")

os.makedirs(os.path.dirname(KNOWLEDGE_JSONL), exist_ok=True)
os.makedirs(KNOWLEDGE_DIR, exist_ok=True)

app = FastAPI(title="Otec Fura API")

# ----------------------------
# Uživatelé / tokeny
# ----------------------------
def _load_users() -> List[Dict[str, Any]]:
    try:
        with open(USERS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

USERS = _load_users()

def _auth_user(auth: Optional[str]) -> Dict[str, Any]:
    if not auth:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = auth
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
    for u in USERS:
        if str(u.get("api_key") or "").strip() == token:
            if not u.get("approved", False):
                raise HTTPException(status_code=403, detail="account not approved")
            return u
    raise HTTPException(status_code=401, detail="Invalid token")

# ----------------------------
# Knowledge indexy
# ----------------------------
STORE = KnowledgeStore(jsonl_path=KNOWLEDGE_JSONL)
DIRIDX = KnowledgeDirIndex(root=KNOWLEDGE_DIR)

def _snippet(txt: str, n: int = 400) -> str:
    txt = re.sub(r"\s+", " ", txt or "").strip()
    if len(txt) <= n:
        return txt
    return txt[:n].rstrip() + "…"

# ----------------------------
# Schémata
# ----------------------------
class AskContext(BaseModel):
    query: str
    top_k: int = 5

class KnowledgeAdd(BaseModel):
    title: str
    content: str
    tags: Optional[List[str]] = None
    private: bool = False

class CrawlIn(BaseModel):
    url: Optional[str] = None
    raw_text: Optional[str] = None
    title: Optional[str] = None
    private: bool = False
    tags: Optional[List[str]] = None

class SearchIn(BaseModel):
    query: str
    top_k: int = 5

# ----------------------------
# Endpoints
# ----------------------------
@app.get("/auth/me")
def auth_me(Authorization: Optional[str] = Header(None)):
    u = _auth_user(Authorization)
    return {"username": u.get("username") or u.get("nick") or "user",
            "email": u.get("email"),
            "approved": True}

@app.post("/get_context")
def get_context(body: AskContext, Authorization: Optional[str] = Header(None)):
    u = _auth_user(Authorization)
    user = u.get("username") or u.get("nick")

    # memory – jednoduchý placeholder (ať UI něco má)
    memory = []
    if os.path.exists("data/public_memory.txt"):
        try:
            with open("data/public_memory.txt", "r", encoding="utf-8") as f:
                mline = f.readline().strip()
                if mline:
                    memory.append(mline)
        except Exception:
            pass

    # knowledge – sloučí JSONL store + složku knowledge/ (i PDF)
    res_store = STORE.search(body.query, top_k=body.top_k, user=user)
    res_dir = DIRIDX.search(body.query, top_k=body.top_k)
    merged = (res_store + res_dir)[:body.top_k]

    knowledge = [
        {
            "title": it.title,
            "source": it.source,
            "snippet": _snippet(it.content)
        }
        for it in merged
    ]

    # embedding – placeholder, aby UI nebylo prázdné
    embedding = [
        "Vítejte v paměti veřejných informací.",
        "Toto je soukromá paměť uživatele Jiri.",
        "Transformers jsou architektura deep learningu založená na mechanismu attention.\n",
    ]

    return {"memory": memory, "knowledge": knowledge, "embedding": embedding}

@app.post("/knowledge/add")
def knowledge_add(body: KnowledgeAdd, Authorization: Optional[str] = Header(None)):
    u = _auth_user(Authorization)
    owner = u.get("username") or u.get("nick")
    it = STORE.add(
        title=body.title,
        content=body.content,
        tags=body.tags or [],
        private=body.private,
        owner=owner,
        source="api"
    )
    return {"ok": True, "id": it.id, "title": it.title}

@app.post("/knowledge/search")
def knowledge_search(body: SearchIn, Authorization: Optional[str] = Header(None)):
    _auth_user(Authorization)
    res_store = STORE.search(body.query, top_k=body.top_k)
    res_dir = DIRIDX.search(body.query, top_k=body.top_k)
    merged = (res_store + res_dir)[:body.top_k]
    return {
        "results": [
            {"title": it.title, "source": it.source, "snippet": _snippet(it.content)}
            for it in merged
        ]
    }

@app.post("/admin/reindex_knowledge")
def reindex_knowledge(Authorization: Optional[str] = Header(None)):
    _auth_user(Authorization)
    DIRIDX.reindex()
    return {"ok": True, "count": len(DIRIDX.docs)}

@app.post("/crawl")
def crawl(body: CrawlIn, Authorization: Optional[str] = Header(None)):
    u = _auth_user(Authorization)
    owner = u.get("username") or u.get("nick")

    # a) přímý text bez URL
    if body.raw_text:
        title = body.title or "Poznámka"
        it = STORE.add(
            title=title,
            content=body.raw_text,
            tags=body.tags or [],
            private=body.private,
            owner=owner,
            source="api:raw_text"
        )
        return {"status": "OK", "chars": len(body.raw_text), "id": it.id}

    # b) URL
    if not body.url:
        raise HTTPException(status_code=400, detail="Missing URL")

    url = body.url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=400, detail="URL must start with http(s)")

    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=CRAWL_TIMEOUT, allow_redirects=True)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Fetch failed: {e}")

    ctype = (r.headers.get("content-type") or "").lower()
    text: Optional[str] = None
    title = body.title

    # PDF?
    if "application/pdf" in ctype or url.lower().endswith(".pdf"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(r.content or b"")
            tmp.flush()
            text = _read_pdf_text(tmp.name)
        if not title:
            title = url.split("/")[-1] or "PDF dokument"
    else:
        # HTML / text
        raw = r.text or ""
        if not title:
            # zkusit <title>
            m = re.search(r"<title[^>]*>(.*?)</title>", raw, flags=re.I | re.S)
            if m:
                title = re.sub(r"\s+", " ", m.group(1)).strip()
        # vyčistit HTML na plain text (hodně jednoduché)
        raw = re.sub(r"(?is)<script.*?>.*?</script>", " ", raw)
        raw = re.sub(r"(?is)<style.*?>.*?</style>", " ", raw)
        raw = re.sub(r"(?is)<[^>]+>", " ", raw)
        text = re.sub(r"\s+", " ", raw).strip()

    if not title:
        title = "Dokument"

    if not text or len(text) < 20:
        raise HTTPException(status_code=400, detail="Extracted text too short")

    it = STORE.add(
        title=title,
        content=text,
        tags=body.tags or [],
        private=body.private,
        owner=owner,
        source=f"url:{url}"
    )
    return {"status": "OK", "chars": len(text), "id": it.id, "title": it.title}
