import os
from typing import List, Optional

import httpx
from fastapi import FastAPI, APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from starlette.responses import RedirectResponse
from starlette.staticfiles import StaticFiles

# Původní jádro FURY (auth, knowledge, get_context atd.)
from main import app as core_app

# ===== Konfigurace z env =====
MODEL_API_BASE = os.getenv("MODEL_API_BASE", "http://100.115.183.37:8095/v1").rstrip("/")
MODEL_API_KEY  = os.getenv("MODEL_API_KEY", "mojelokalnikurvitko")
MODEL_DEFAULT  = os.getenv("MODEL_DEFAULT", "llama3:8b")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "120"))

FURA_API_KEY = os.getenv("FURA_API_KEY", "")
FURA_AUTH_REQUIRED = os.getenv("FURA_AUTH_REQUIRED", "1") not in ("0", "false", "False", "")

WEBUI_DIR = os.path.join(os.path.dirname(__file__), "webui")

# ===== MODELY REQUESTŮ =====
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

# ===== AUTH DEPENDENCE =====
def require_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    if not FURA_AUTH_REQUIRED:
        return
    if not FURA_API_KEY or x_api_key != FURA_API_KEY:
        raise HTTPException(status_code=401, detail="Chybí nebo neplatný API klíč")

# ===== APLIKACE =====
app = FastAPI(title="Otec Fura", docs_url="/docs", redoc_url="/redoc")
app.mount("/core", core_app)  # aby zůstaly staré routy

router = APIRouter()

# Healthz
@router.get("/healthz")
async def healthz():
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(MODEL_API_BASE.rsplit("/", 1)[0] + "/healthz")
            gw = r.json()
    except Exception:
        gw = {"ok": False}
    return {"app": "otec-fura", "ok": True, "model_gateway": gw}

# /ask – jednoduché rozhraní
@router.post("/ask", dependencies=[Depends(require_api_key)])
async def ask(req: AskReq):
    body = {
        "model": req.model or MODEL_DEFAULT,
        "messages": [{"role": "user", "content": req.message}],
        "temperature": req.temperature,
    }
    headers = {"Authorization": f"Bearer {MODEL_API_KEY}"}
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            r = await client.post(f"{MODEL_API_BASE}/chat/completions", json=body, headers=headers)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Model API {e.response.status_code}: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Model API chyba: {e}")
    msg = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
    return {"response": msg}

# /v1/chat – OpenAI kompatibilní endpoint
@router.post("/v1/chat", dependencies=[Depends(require_api_key)])
async def v1_chat(req: ChatReq):
    body = {
        "model": req.model or MODEL_DEFAULT,
        "messages": [m.model_dump() for m in req.messages],
        "temperature": req.temperature,
    }
    headers = {"Authorization": f"Bearer {MODEL_API_KEY}"}
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            r = await client.post(f"{MODEL_API_BASE}/chat/completions", json=body, headers=headers)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Model API {e.response.status_code}: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Model API chyba: {e}")
    msg = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
    return {"answer": msg, "raw": data}

# UI na /app
if os.path.isdir(WEBUI_DIR):
    app.mount("/app", StaticFiles(directory=WEBUI_DIR, html=True), name="app")

@router.get("/")
async def root_redirect():
    return RedirectResponse("/app/")

# Připojit router
app.include_router(router)
