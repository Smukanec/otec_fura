import os
from typing import List, Optional

import httpx
from fastapi import FastAPI, APIRouter, HTTPException, Header
from pydantic import BaseModel
from starlette.responses import RedirectResponse
from starlette.staticfiles import StaticFiles

# === Konfigurace z env ===
MODEL_API_BASE = os.getenv("MODEL_API_BASE", "http://100.115.183.37:8095/v1").rstrip("/")
MODEL_API_KEY = os.getenv("MODEL_API_KEY", "mojelokalnikurvitko")
MODEL_DEFAULT = os.getenv("MODEL_DEFAULT", "llama3:8b")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "120"))

# === Základní FastAPI app ===
app = FastAPI(title="Otec Fura", version="0.1.0")
router = APIRouter()

# === Schémata ===
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

# === Helpery ===
def require_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    if not MODEL_API_KEY:
        return  # žádný klíč nenastaven => bez kontroly
    if x_api_key != MODEL_API_KEY:
        raise HTTPException(status_code=401, detail="Chybí API klíč nebo je neplatný")

async def call_model_api(payload: dict) -> dict:
    headers = {
        "Authorization": f"Bearer {MODEL_API_KEY}" if MODEL_API_KEY else "",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        r = await client.post(f"{MODEL_API_BASE}/chat/completions", json=payload, headers=headers)
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Model API error {r.status_code}: {r.text}")
        return r.json()

# === Healthz ===
@app.get("/healthz")
async def healthz():
    # zkusně pingneme model gateway
    gw = None
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            rr = await client.get(MODEL_API_BASE.rsplit("/", 1)[0].rstrip("/") + "/healthz")
            if rr.status_code == 200:
                gw = rr.json()
    except Exception:
        gw = None
    return {"app": "otec-fura", "ok": True, "model_gateway": gw}

# === /ask: jednoduché rozhraní (message -> response) ===
@router.post("/ask", dependencies=[Depends(require_api_key)])
async def ask(req: AskReq):
    model = (req.model or MODEL_DEFAULT).strip()
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": req.message}],
        "temperature": req.temperature,
    }
    data = await call_model_api(payload)
    try:
        content = data["choices"][0]["message"]["content"]
    except Exception:
        content = str(data)
    return {"response": content, "model": model}

# === /v1/chat: OpenAI-like mini compat ===
@router.post("/v1/chat", dependencies=[Depends(require_api_key)])
async def v1_chat(req: ChatReq):
    model = (req.model or MODEL_DEFAULT).strip()
    payload = {
        "model": model,
        "messages": [m.dict() for m in req.messages],
        "temperature": req.temperature,
    }
    data = await call_model_api(payload)
    try:
        content = data["choices"][0]["message"]["content"]
    except Exception:
        content = str(data)
    return {"answer": content, "raw": data, "model": model}

# === root redirect => /app (statika) ===
@app.get("/")
async def root():
    return RedirectResponse("/app")

# mount statické UI (pokud složka existuje)
WEBUI_DIR = os.path.join(os.path.dirname(__file__), "webui")
if os.path.isdir(WEBUI_DIR):
    app.mount("/app", StaticFiles(directory=WEBUI_DIR, html=True), name="app")

# přimontuj router
app.include_router(router)
