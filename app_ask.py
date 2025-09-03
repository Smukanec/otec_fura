import os
from typing import List, Optional

import httpx
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from starlette.responses import RedirectResponse
from starlette.staticfiles import StaticFiles

# === Konfigurace ===
WEBUI_DIR = os.path.join(os.path.dirname(__file__), "webui")

MODEL_API_BASE = os.getenv("MODEL_API_BASE", "http://100.115.183.37:8095/v1").rstrip("/")
MODEL_API_KEY  = os.getenv("MODEL_API_KEY",  "mojelokalnikurvitko")
DEFAULT_MODEL  = os.getenv("MODEL_DEFAULT",  "llama3:8b")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "120"))

# Volitelné API‑klíčování (když proměnná není nastavena, endpoints jsou otevřené)
FURA_API_KEY = os.getenv("FURA_API_KEY")

def require_api_key(x_api_key: Optional[str] = Header(None)):
    if FURA_API_KEY and x_api_key != FURA_API_KEY:
        raise HTTPException(status_code=401, detail="Chybí nebo špatný API klíč")

# === Datové modely ===
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

# === Aplikace ===
app = FastAPI(title="Otec Fura", version="1.0.0")
router = APIRouter()

# Zdraví + kontrola model gateway
@app.get("/healthz")
def healthz():
    try:
        r = httpx.get(MODEL_API_BASE.replace("/v1", "") + "/healthz", timeout=5)
        ok = (r.status_code == 200)
        mg = r.json() if ok else {"ok": False, "status": r.status_code}
    except Exception as e:
        ok = False
        mg = {"ok": False, "error": str(e)}
    return {"app": "otec-fura", "ok": ok, "model_gateway": mg}

# Pomocná funkce pro volání /v1/chat/completions na gateway
def call_chat_completions(model: str, messages: List[dict], temperature: float):
    headers = {
        "Authorization": f"Bearer {MODEL_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    r = httpx.post(
        f"{MODEL_API_BASE}/chat/completions",
        json=payload,
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Upstream error: {r.text}")
    data = r.json()
    # OpenAI‑like extrakce
    text = (data.get("choices") or [{}])[0].get("message", {}).get("content")
    if not text:
        raise HTTPException(status_code=502, detail="Unexpected upstream payload")
    return data, text

# Jednoduché /ask
@router.post("/ask", dependencies=[Depends(require_api_key)] if FURA_API_KEY else None)
def ask(req: AskReq):
    _, text = call_chat_completions(
        req.model or DEFAULT_MODEL,
        [{"role": "user", "content": req.message}],
        req.temperature,
    )
    return {"response": text}

# OpenAI‑like vstup, vrací navíc "answer" pro pohodlí UI
@router.post("/v1/chat", dependencies=[Depends(require_api_key)] if FURA_API_KEY else None)
def v1_chat(req: ChatReq):
    data, text = call_chat_completions(
        req.model or DEFAULT_MODEL,
        [m.model_dump() for m in req.messages],
        req.temperature,
    )
    return {
        "id": data.get("id", "fura-proxy"),
        "object": "chat.completion",
        "created": data.get("created"),
        "model": req.model or DEFAULT_MODEL,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": text}}],
        "answer": text,
    }

app.include_router(router)

# === UI mount ===
if os.path.isdir(WEBUI_DIR):
    app.mount("/app", StaticFiles(directory=WEBUI_DIR, html=True), name="app")

# Redirecty se správným slash
@app.get("/", include_in_schema=False)
def _root():
    return RedirectResponse(url="/app/", status_code=308)

@app.get("/app", include_in_schema=False)
def _app_noslash():
    return RedirectResponse(url="/app/", status_code=308)
