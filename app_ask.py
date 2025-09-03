#!/usr/bin/env python3
import os
from typing import List, Optional

import httpx
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Header
from fastapi.responses import RedirectResponse
from starlette.staticfiles import StaticFiles
from pydantic import BaseModel

# ===== Konfigurace =====
APP_NAME = "Otec Fura"
APP_VERSION = os.getenv("FURA_VERSION", "1.0.0")

MODEL_API_BASE = os.getenv("MODEL_API_BASE", "http://100.115.183.37:8095/v1").rstrip("/")
MODEL_API_KEY  = os.getenv("MODEL_API_KEY", "mojelokalnikurvitko")
DEFAULT_MODEL  = os.getenv("MODEL_DEFAULT", "llama3:8b")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "120"))
# root URL model gateway (pro /healthz)
GW_ROOT = MODEL_API_BASE[:-3] if MODEL_API_BASE.endswith("/v1") else MODEL_API_BASE

# volitelně ochrana FURY vlastním klíčem (pokud proměnná není nastavena, klíč se NEvyžaduje)
FURA_API_KEY = os.getenv("FURA_API_KEY", "").strip()

# ===== FastAPI =====
app = FastAPI(title=APP_NAME, version=APP_VERSION)
router = APIRouter()

# ===== Modely požadavků =====
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatReq(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    temperature: Optional[float] = 0.5

class AskReq(BaseModel):
    message: str
    model: Optional[str] = None
    temperature: Optional[float] = 0.5

# ===== Autorizace pro FURU (X-API-Key) – volitelná =====
def require_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> str:
    if FURA_API_KEY:  # jen pokud je ochrana zapnutá
        if not x_api_key or x_api_key != FURA_API_KEY:
            raise HTTPException(status_code=401, detail="Chybí API klíč")
    return x_api_key or ""

# ===== Pomocné volání na model gateway =====
def _model_headers() -> dict:
    return {
        "Authorization": f"Bearer {MODEL_API_KEY}",
        "Content-Type": "application/json",
    }

def _call_model(messages: List[dict], model: Optional[str], temperature: float) -> str:
    url = f"{MODEL_API_BASE}/chat/completions"
    payload = {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        r = client.post(url, headers=_model_headers(), json=payload)
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=f"Model gateway error: {r.text}")
        data = r.json()
    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        raise HTTPException(status_code=502, detail=f"Unexpected model response: {data!r}")

# ===== Endpoints =====
@app.get("/healthz")
def healthz():
    gw = {"ok": False}
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{GW_ROOT}/healthz")
            resp.raise_for_status()
            gw = resp.json()
            gw["ok"] = True
    except Exception as e:
        gw = {"ok": False, "error": str(e)}
    return {"app": "otec-fura", "ok": True, "model_gateway": gw}

@router.post("/ask", dependencies=[Depends(require_api_key)])
def ask(req: AskReq):
    answer = _call_model(
        messages=[{"role": "user", "content": req.message}],
        model=req.model,
        temperature=req.temperature or 0.5,
    )
    return {"response": answer}

@router.post("/v1/chat", dependencies=[Depends(require_api_key)])
def v1_chat(req: ChatReq):
    answer = _call_model(
        messages=[m.model_dump() for m in req.messages],
        model=req.model,
        temperature=req.temperature or 0.5,
    )
    return {"answer": answer, "model": req.model or DEFAULT_MODEL}

# Swagger je na /docs, UI na /app, root -> /app
app.include_router(router)
app.mount("/app", StaticFiles(directory="webui", html=True), name="app")

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/app")
