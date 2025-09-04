# -*- coding: utf-8 -*-
import os
from typing import List, Optional, Dict, Any

import httpx
from fastapi import FastAPI, APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel, Field
from starlette.responses import RedirectResponse, HTMLResponse
from starlette.staticfiles import StaticFiles

APP_NAME = "otec-fura"
MODEL_API_BASE = os.getenv("MODEL_API_BASE", "http://100.115.183.37:8095/v1")
MODEL_API_KEY_ENV = os.getenv("MODEL_API_KEY", "")  # volitelné, lze přebít X-API-Key

# -------------------- Pydantic schémata --------------------

class AskReq(BaseModel):
    message: str = Field(..., description="Uživatelský dotaz")
    model: str = Field(..., description="Model v model-gateway (např. llama3:8b)")
    temperature: Optional[float] = Field(0.2, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1)

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatReq(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.2
    max_tokens: Optional[int] = None

# -------------------- FastAPI app --------------------

app = FastAPI(title="Otec Fura", version="1.0.0")
router = APIRouter()

# Root -> /app/ (trvale)
@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/app/")

# Zdraví aplikace + model-gateway
@router.get("/healthz")
async def healthz():
    ok = True
    mgw_info: Dict[str, Any] = {"ok": False}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{MODEL_API_BASE.rstrip('/')}/healthz")
            if r.status_code == 200:
                mgw_info = r.json()
                mgw_info["ok"] = True
            else:
                ok = False
    except Exception:
        ok = False
    return {"app": APP_NAME, "ok": ok, "model_gateway": mgw_info}

# --- pomocná funkce na získání API klíče z hlavičky či env ---
async def require_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> str:
    # povolím prázdné (bezpečnost si řešíš Caddy/místní síť)
    return x_api_key or MODEL_API_KEY_ENV or ""

# Jednoduché /ask
@router.post("/ask")
async def ask(req: AskReq, api_key: str = Depends(require_api_key)):
    payload = {
        "model": req.model,
        "messages": [{"role": "user", "content": req.message}],
        "temperature": req.temperature,
    }
    if req.max_tokens:
        payload["max_tokens"] = req.max_tokens

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{MODEL_API_BASE.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
            )
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        data = r.json()
        # kompatibilita s OpenAI-like shape
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        ) or data.get("answer") or ""
        return {"response": content}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# OpenAI-like /v1/chat
@router.post("/v1/chat")
async def v1_chat(req: ChatReq, api_key: str = Depends(require_api_key)):
    payload = req.dict(exclude_none=True)
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{MODEL_API_BASE.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
            )
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        data = r.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        ) or data.get("answer") or ""
        # sjednotím výstup
        return {"answer": content, "raw": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

app.include_router(router)

# -------------------- Statické UI --------------------

# /app/ -> jednoduché UI z webui/
STATIC_DIR = os.path.join(os.path.dirname(__file__), "webui")
if os.path.isdir(STATIC_DIR):
    app.mount("/app", StaticFiles(directory=STATIC_DIR, html=True), name="app")
else:
    @app.get("/app", include_in_schema=False)
    async def app_placeholder():
        return HTMLResponse("<h1>UI nenalezeno</h1><p>Chybí adresář webui/.</p>")
