import os
from typing import List, Optional

import httpx
from fastapi import FastAPI, APIRouter, HTTPException, Header
from pydantic import BaseModel
from starlette.responses import RedirectResponse, HTMLResponse
from starlette.staticfiles import StaticFiles

# --- core app (původní Fura routery) ---
from main import app as core_app

app = core_app
router = APIRouter()

MODEL_API_BASE = os.getenv("MODEL_API_BASE", "http://100.115.183.37:8095/v1").rstrip("/")
MODEL_API_KEY  = os.getenv("MODEL_API_KEY",  "mojelokalnikurvitko")
MODEL_DEFAULT  = os.getenv("MODEL_DEFAULT",  "llama3:8b")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "120"))

# ---------- datové modely ----------
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

# ---------- health ----------
@router.get("/healthz")
async def healthz():
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{MODEL_API_BASE.rsplit('/',1)[0]}/healthz")
            gw = r.json()
        return {"app": "otec-fura", "ok": True, "model_gateway": gw}
    except Exception as e:
        return {"app": "otec-fura", "ok": False, "error": str(e)}

# ---------- proxy: seznam modelů z gatewaye ----------
@router.get("/v1/models")
async def list_models(x_api_key: Optional[str] = Header(None)):
    api_key = x_api_key or MODEL_API_KEY
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        r = await client.get(f"{MODEL_API_BASE}/models", headers=headers)
        if r.status_code >= 400:
            raise HTTPException(r.status_code, r.text)
        return r.json()

# ---------- /v1/chat (OpenAI-like) ----------
@router.post("/v1/chat")
async def v1_chat(req: ChatReq, x_api_key: Optional[str] = Header(None)):
    model = (req.model or MODEL_DEFAULT)
    payload = {"model": model, "messages": [m.dict() for m in req.messages]}
    if req.temperature is not None:
        payload["temperature"] = req.temperature

    headers = {
        "Authorization": f"Bearer {(x_api_key or MODEL_API_KEY)}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        r = await client.post(f"{MODEL_API_BASE}/chat/completions", json=payload, headers=headers)
        if r.status_code >= 400:
            raise HTTPException(r.status_code, r.text)
        data = r.json()

    # zjednodušená odpověď
    msg = (data.get("choices") or [{}])[0].get("message", {}).get("content")
    return {"answer": msg, "raw": data}

# ---------- /ask (jednoduchá JSON obálka) ----------
@router.post("/ask")
async def ask(req: AskReq, x_api_key: Optional[str] = Header(None)):
    return await v1_chat(
        ChatReq(messages=[ChatMessage(role="user", content=req.message)],
                model=req.model or MODEL_DEFAULT,
                temperature=req.temperature),
        x_api_key=x_api_key
    )

# ---------- mount UI a kořen ----------
app.mount("/app", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "webui"), html=True), name="app")

@router.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/app/")

app.include_router(router)
