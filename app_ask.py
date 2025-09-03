# -*- coding: utf-8 -*-
"""
Otec Fura – lehký FastAPI wrapper:
- /healthz            : health + ping na model-gateway
- /app/*              : statické UI
- /ask                : jednoduchý chat endpoint (message + model)
- /v1/chat            : OpenAI-like endpoint (model + messages[])
"""

import os
from typing import List, Optional, Dict, Any

import httpx
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Header
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------
# Konfigurace z prostředí
# ---------------------------------------------------------------------
APP_NAME = "otec-fura"

MODEL_API_BASE = os.getenv("MODEL_API_BASE", "http://100.115.183.37:8095/v1").rstrip("/")
MODEL_API_KEY = os.getenv("MODEL_API_KEY", "")  # klíč k model gateway (Authorization: Bearer …)

# Volitelná ochrana vlastním API klíčem (FURA_API_KEY).
# Když proměnná chybí/je prázdná, ochrana se nevymáhá.
FURA_API_KEY = os.getenv("FURA_API_KEY", "").strip()

WEBUI_DIR = os.path.join(os.path.dirname(__file__), "webui")

# ---------------------------------------------------------------------
# Pydantic schémata
# ---------------------------------------------------------------------
class AskReq(BaseModel):
    message: str = Field(..., description="Uživatelský dotaz/hláška")
    model: str = Field(..., description="Identifikátor modelu (např. llama3:8b)")
    temperature: Optional[float] = Field(0.2, ge=0.0, le=2.0)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatReq(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.2


# ---------------------------------------------------------------------
# App + router
# ---------------------------------------------------------------------
app = FastAPI(title="Otec Fura", version="1.0.0", openapi_url="/openapi.json")
router = APIRouter()


# --- volitelná ochrana vlastním API klíčem ---------------------------
def require_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    if not FURA_API_KEY:
        return  # ochrana vypnuta
    if x_api_key != FURA_API_KEY:
        raise HTTPException(status_code=401, detail="Chybí nebo nesedí X-API-Key")


# --- pomocné ----------------------------------------------------------
def _model_headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if MODEL_API_KEY:
        headers["Authorization"] = f"Bearer {MODEL_API_KEY}"
    return headers


async def _gateway_health() -> Dict[str, Any]:
    url = f"{MODEL_API_BASE}/healthz"
    try:
        async with httpx.AsyncClient(timeout=5) as cx:
            r = await cx.get(url)
            r.raise_for_status()
            data = r.json()
            data["ok"] = True
            return data
    except Exception:
        return {"ok": False}


async def _chat_completion(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Proxy na model gateway (OpenAI-like /v1/chat/completions)."""
    url = f"{MODEL_API_BASE}/chat/completions"
    async with httpx.AsyncClient(timeout=60) as cx:
        r = await cx.post(url, json=payload, headers=_model_headers())
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()


# ---------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------
@router.get("/healthz")
async def healthz():
    gw = await _gateway_health()
    return JSONResponse(
        {
            "app": APP_NAME,
            "ok": True,
            "model_gateway": gw,
        }
    )


@router.get("/", include_in_schema=False)
async def root_redirect():
    # vždy s trailing slash, aby dobře fungovaly relativní cesty v /app/
    return RedirectResponse(url="/app/", status_code=308)


# Jednoduché UI (statika)
app.mount("/app", StaticFiles(directory=WEBUI_DIR, html=True), name="app")


@router.post("/ask", dependencies=[Depends(require_api_key)])
async def ask(req: AskReq):
    payload = {
        "model": req.model,
        "messages": [
            {"role": "user", "content": req.message}
        ],
        "temperature": req.temperature,
    }
    data = await _chat_completion(payload)
    # očekáváme choices[0].message.content
    try:
        answer = data["choices"][0]["message"]["content"]
    except Exception:
        answer = data  # fallback – pošli raw
    return {"response": answer}


@router.post("/v1/chat", dependencies=[Depends(require_api_key)])
async def v1_chat(req: ChatReq):
    payload = req.dict()
    data = await _chat_completion(payload)
    try:
        answer = data["choices"][0]["message"]["content"]
    except Exception:
        answer = data
    return {"answer": answer, "raw": data}


app.include_router(router)
