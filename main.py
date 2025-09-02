# -*- coding: utf-8 -*-
import os, json, logging
from typing import Optional, List
from fastapi import FastAPI, Depends, Request, HTTPException, Header
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from knowledge_store import KnowledgeStore
from api.auth import router as auth_router
from api.user_endpoint import router as user_router
from api.get_context import router as context_router
from api.crawler_router import router as crawler_router
from middleware import APIKeyAuthMiddleware, refresh_users

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("fura")

APP_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(APP_DIR, "data")
KNOW_DIR = os.path.join(APP_DIR, "knowledge")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(KNOW_DIR, exist_ok=True)


def _load_users() -> List[dict]:
    return refresh_users()

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

app.include_router(auth_router)
app.include_router(user_router)
app.include_router(context_router)
app.include_router(crawler_router)
app.add_middleware(
    APIKeyAuthMiddleware,
    allow_paths={"/auth/register", "/auth/token", "/v1/chat", "/ask", "/v1/models"},
)


@app.get("/")
async def root():
    return {"message": "Otec Fura API"}

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

