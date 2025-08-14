# -*- coding: utf-8 -*-
import os, json, logging
from typing import Optional, List
from fastapi import FastAPI, Depends, Request, HTTPException, Header
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from knowledge_store import KnowledgeStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("fura")

APP_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(APP_DIR, "data")
KNOW_DIR = os.path.join(APP_DIR, "knowledge")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(KNOW_DIR, exist_ok=True)

USERS_FILE = os.path.join(DATA_DIR, "users.json")
if not os.path.exists(USERS_FILE):
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    # demo user
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump([{
            "username":"demo",
            "email":"demo@example.com",
            "approved": True,
            "api_key": "demo"
        }], f, ensure_ascii=False, indent=2)

def _load_users() -> List[dict]:
    try:
        return json.load(open(USERS_FILE, "r", encoding="utf-8"))
    except Exception:
        return []

def _find_user_by_token(token: str) -> Optional[dict]:
    token = (token or "").strip()
    if not token: return None
    for u in _load_users():
        if u.get("api_key") == token and u.get("approved", False):
            return u
    return None

def _auth_headers_to_token(auth: Optional[str]) -> Optional[str]:
    if not auth: return None
    a = auth.strip()
    if a.lower().startswith("bearer "):
        return a.split(" ",1)[1].strip()
    return a

async def current_user(authorization: Optional[str]=Header(None)):
    token = _auth_headers_to_token(authorization)
    u = _find_user_by_token(token or "")
    if not u:
        raise HTTPException(status_code=401, detail="Neplatný token")
    return u

app = FastAPI(title="Fura API", version="1.0.0")
ks = KnowledgeStore(APP_DIR)

class AddNote(BaseModel):
    title: str
    content: str
    tags: Optional[List[str]] = None

class SearchReq(BaseModel):
    query: str
    top_k: int = 5

class CrawlReq(BaseModel):
    url: Optional[str] = None
    raw_text: Optional[str] = None
    title: Optional[str] = None
    tags: Optional[List[str]] = None

@app.get("/auth/me")
async def auth_me(u=Depends(current_user)):
    return {"username": u["username"], "email": u.get("email",""), "approved": True}

@app.post("/knowledge/add")
async def knowledge_add(body: AddNote, u=Depends(current_user)):
    doc_id, chunks = ks.add_manual(body.title, body.content, body.tags or [])
    return {"ok": True, "id": doc_id, "title": body.title, "chunks": chunks}

@app.post("/admin/reindex_knowledge")
async def admin_reindex(u=Depends(current_user)):
    res = ks.reindex_folder(KNOW_DIR)
    return {"ok": True, **res}

@app.post("/knowledge/search")
async def knowledge_search(req: SearchReq, u=Depends(current_user)):
    hits = ks.search(req.query, top_k=max(1, min(20, req.top_k)))
    return {"results": hits}

@app.post("/crawl")
async def crawl(req: CrawlReq, u=Depends(current_user)):
    if req.raw_text:
        title = req.title or "Interní poznámka"
        doc_id, chunks = ks.add_manual(title, req.raw_text, req.tags or ["note"])
        return {"ok": True, "mode": "raw_text", "id": doc_id, "title": title, "chunks": chunks}
    if req.url:
        try:
            doc_id, chunks = ks.add_from_url(req.url)
            return {"ok": True, "mode": "url", "id": doc_id, "title": req.url, "chunks": chunks}
        except Exception as e:
            log.exception("crawl failed: %s", e)
            raise HTTPException(status_code=400, detail=f"Failed to crawl")
    raise HTTPException(status_code=400, detail="Missing URL or raw_text")

@app.post("/get_context")
async def get_context(req: SearchReq, u=Depends(current_user)):
    # public memory
    mem_path = os.path.join(APP_DIR, "memory", "public.jsonl")
    memory = []
    if os.path.exists(mem_path):
        with open(mem_path, "r", encoding="utf-8") as f:
            memory = [line.strip() for line in f if line.strip()]
    else:
        os.makedirs(os.path.dirname(mem_path), exist_ok=True)
        with open(mem_path, "a", encoding="utf-8") as f:
            f.write("Vítejte v paměti veřejných informací.\n")
        memory = ["Vítejte v paměti veřejných informací."]

    knowledge = ks.search(req.query, top_k=max(1, min(10, req.top_k)))
    # a pár demonstračních „embedding“ řádků jako dřív:
    embedding = [
        "Vítejte v paměti veřejných informací.",
        "Toto je soukromá paměť uživatele Jiri.",
        "Transformers jsou architektura deep learningu založená na mechanismu attention.\n"
    ]
    return {"memory": memory, "knowledge": knowledge, "embedding": embedding}
