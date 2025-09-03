import os
from typing import List, Optional

import httpx
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from starlette.responses import RedirectResponse, HTMLResponse
from starlette.staticfiles import StaticFiles

# === Konfigurace ===
MODEL_API_BASE = os.getenv("MODEL_API_BASE", "http://100.115.183.37:8095/v1").rstrip("/")
MODEL_API_KEY  = os.getenv("MODEL_API_KEY",  "mojelokalnikurvitko")
MODEL_DEFAULT  = os.getenv("MODEL_DEFAULT",  "llama3:8b")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "120"))
FURA_API_KEY   = os.getenv("FURA_API_KEY")  # když je nastaven, vyžadujeme X-API-Key

# === FastAPI + statické UI ===
app = FastAPI(title="Otec Fura", version="1.0.0", docs_url="/docs", redoc_url=None)

APP_DIR   = os.path.dirname(__file__)
WEBUI_DIR = os.path.join(APP_DIR, "webui")
if os.path.isdir(WEBUI_DIR):
    # /app/ bude servírovat index.html (html=True)
    app.mount("/app", StaticFiles(directory=WEBUI_DIR, html=True), name="app")

# root → /app/ (ať je to blbuvzdorné)
@app.get("/", include_in_schema=False)
async def root_redirect():
    return RedirectResponse(url="/app/")

# /app bez lomítka → /app/
@app.get("/app", include_in_schema=False)
async def app_slash_redirect():
    return RedirectResponse(url="/app/")

router = APIRouter()

# === Modely požadavků ===
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

# === Jednoduchá kontrola API klíče ===
def require_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    if FURA_API_KEY:
        if not x_api_key or x_api_key != FURA_API_KEY:
            raise HTTPException(status_code=401, detail="Chybí API klíč")

# === /healthz ===
@app.get("/healthz")
async def healthz():
    # pokud MODEL_API_BASE končí /v1 → health je o adresář výš
    mg_root = MODEL_API_BASE[:-3] if MODEL_API_BASE.endswith("/v1") else MODEL_API_BASE
    mg = {}
    ok = True
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{mg_root}/healthz")
            if r.status_code == 200:
                mg = r.json()
            else:
                ok = False
    except Exception:
        ok = False
    return {"app": "otec-fura", "ok": ok, "model_gateway": mg or {"ok": ok}}

# === /ask → jednoduché rozhraní (message -> response) ===
@router.post("/ask", dependencies=[Depends(require_api_key)])
async def ask(req: AskReq):
    model = (req.model or MODEL_DEFAULT).strip()
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": req.message}],
    }
    headers = {"Authorization": f"Bearer {MODEL_API_KEY}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        r = await client.post(f"{MODEL_API_BASE}/chat/completions", headers=headers, json=payload)
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Model error: {r.text}")
        data = r.json()
    # vytáhneme text z OpenAI-like odpovědi
    try:
        text = data["choices"][0]["message"]["content"]
    except Exception:
        text = data.get("detail") or str(data)
    return {"response": text, "raw": data.get("usage")}

# === /v1/chat (OpenAI-like) ===
@router.post("/v1/chat", dependencies=[Depends(require_api_key)])
async def v1_chat(req: ChatReq):
    model = (req.model or MODEL_DEFAULT).strip()
    payload = {
        "model": model,
        "messages": [m.model_dump() for m in req.messages],
        "temperature": req.temperature,
    }
    headers = {"Authorization": f"Bearer {MODEL_API_KEY}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        r = await client.post(f"{MODEL_API_BASE}/chat/completions", headers=headers, json=payload)
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Model error: {r.text}")
        data = r.json()
    try:
        text = data["choices"][0]["message"]["content"]
    except Exception:
        text = None
    return {"answer": text, "raw": data}

# zaregistrovat router
app.include_router(router)
