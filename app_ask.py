import os
from typing import List, Optional

import httpx
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from starlette.responses import RedirectResponse
from starlette.staticfiles import StaticFiles

# --- Konfigurace z ENV ---
BASE_DIR = os.path.dirname(__file__)
WEBUI_DIR = os.getenv("WEBUI_DIR", os.path.join(BASE_DIR, "webui"))

MODEL_API_BASE = os.getenv("MODEL_API_BASE", "http://100.115.183.37:8095/v1").rstrip("/")
MODEL_API_KEY  = os.getenv("MODEL_API_KEY",  "")
MODEL_DEFAULT  = os.getenv("MODEL_DEFAULT",  "llama3:8b")
FURA_API_KEY   = os.getenv("FURA_API_KEY",   "")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "120"))

# --- Aplikace ---
app = FastAPI(title="Otec Fura", version="1.0.0", docs_url="/docs", redoc_url=None)
router = APIRouter()

# Statický web na /app
os.makedirs(WEBUI_DIR, exist_ok=True)
app.mount("/app", StaticFiles(directory=WEBUI_DIR, html=True), name="webui")

# Kořen -> /app/ (UI)
@app.get("/", include_in_schema=False)
async def root_redirect():
    return RedirectResponse(url="/app/")

# --- Bezpečnost: volitelný API klíč ---
async def require_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    if FURA_API_KEY and x_api_key != FURA_API_KEY:
        raise HTTPException(status_code=401, detail="Chybí nebo neplatný API klíč")

# --- Model health (volitelně volá gateway /healthz) ---
def _model_health():
    base = MODEL_API_BASE
    if base.endswith("/v1"):
        base = base[:-3]
    url = f"{base}/healthz"
    try:
        r = httpx.get(url, timeout=10.0)
        j = r.json()
        j["ok"] = (r.status_code == 200)
        return j
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/healthz", include_in_schema=False)
async def healthz():
    return {"app": "otec-fura", "ok": True, "model_gateway": _model_health()}

# --- Pydantic modely ---
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

# --- volání model gateway ---
async def _chat_completions(payload: dict) -> dict:
    headers = {"Content-Type": "application/json"}
    if MODEL_API_KEY:
        headers["Authorization"] = f"Bearer {MODEL_API_KEY}"
    url = f"{MODEL_API_BASE}/chat/completions"
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        r = await client.post(url, json=payload, headers=headers)
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Model gateway error: {r.text}")
        return r.json()

@router.post("/v1/chat", dependencies=[Depends(require_api_key)])
async def v1_chat(req: ChatReq):
    model = req.model or MODEL_DEFAULT
    payload = {"model": model, "messages": [m.model_dump() for m in req.messages], "temperature": req.temperature}
    data = await _chat_completions(payload)
    # kompatibilní jednoduchá odpověď:
    answer = None
    try:
        answer = data["choices"][0]["message"]["content"]
    except Exception:
        pass
    return {"answer": answer, "raw": data}

@router.post("/ask", dependencies=[Depends(require_api_key)])
async def ask(req: AskReq):
    model = req.model or MODEL_DEFAULT
    payload = {"model": model, "messages": [{"role": "user", "content": req.message}], "temperature": req.temperature}
    data = await _chat_completions(payload)
    try:
        text = data["choices"][0]["message"]["content"]
    except Exception:
        text = str(data)
    return {"response": text}

app.include_router(router)
