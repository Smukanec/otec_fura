# app_ask.py
# Drop-in „vstupní bod“ pro Otec Fura:
# - načte existující FastAPI aplikaci z main.py
# - přidá kompatibilní endpoint /ask (stejné schéma jako staré UI)
# - přidá /v1/chat (OpenAI-like chat) a volá model gateway na Jarviku
# - nechává všechny původní endpointy (auth, knowledge, crawl...) beze změny

import os
import urllib.parse
from typing import List, Optional

import httpx
from fastapi import APIRouter, FastAPI, HTTPException
from models_meta import ALLOWED_MODELS

# Připojíme existující app z tvého projektu
from main import app as base_app  # main:app už běží v projektu

app: FastAPI = base_app
router = APIRouter()

# ====== Konfigurace z ENV (nastavíme v /etc/otec-fura/.env) ======
MODEL_API_BASE = os.getenv("MODEL_API_BASE", "http://100.115.183.37:8095/v1").rstrip("/")
MODEL_API_KEY = os.getenv("MODEL_API_KEY")
if not MODEL_API_KEY:
    raise RuntimeError(
        "MODEL_API_KEY environment variable is required on startup."
    )
MODEL_DEFAULT = os.getenv("MODEL_DEFAULT", "llama3:8b")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "120"))

# ====== Datové modely ======
from pydantic import BaseModel

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


# ====== Pomocné funkce ======
async def _maybe_context(query: str) -> list[str]:
    """
    Zkusí vytáhnout kontext z místního /get_context (pokud existuje).
    Když to spadne, prostě vrátí [] a jedeme dál.
    """
    ctx: list[str] = []
    get_url = f"http://127.0.0.1:8090/get_context?query={urllib.parse.quote(query)}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(get_url)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, dict):
                    for key in ("context", "chunks", "results", "items"):
                        if key in data and isinstance(data[key], list):
                            ctx = [str(x) for x in data[key]][:4]
                            break
                elif isinstance(data, list):
                    ctx = [str(x) for x in data][:4]
    except Exception:
        pass
    if not ctx:
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.post(
                    "http://127.0.0.1:8090/get_context",
                    json={"query": query, "top_k": 4},
                )
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, dict):
                        for key in ("context", "chunks", "results", "items"):
                            if key in data and isinstance(data[key], list):
                                ctx = [str(x) for x in data[key]][:4]
                                break
                    elif isinstance(data, list):
                        ctx = [str(x) for x in data][:4]
        except Exception:
            pass
    return ctx


async def _call_model_gateway(messages: list[dict], model: str, temperature: float) -> dict:
    """
    Volá Jarvikovu model gateway (OpenAI-compatible /v1/chat/completions).
    Vrací JSON odpovědi.
    """
    url = f"{MODEL_API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {MODEL_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as c:
        r = await c.post(url, headers=headers, json=payload)
        if r.status_code >= 400:
            # přepošleme detail dál jako 502
            raise HTTPException(status_code=502, detail=r.text)
        return r.json()


def _extract_text(openai_like: dict) -> str:
    try:
        return openai_like.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
    except Exception:
        return ""


def _validate_model(model: str) -> None:
    if model not in ALLOWED_MODELS:
        raise HTTPException(status_code=400, detail=f"Unsupported model: {model}")


# ====== /healthz ======
@router.get("/healthz")
async def healthz():
    return {"status": "ok"}


# ====== /v1/models ======
@router.get("/v1/models")
async def v1_models():
    """List available models.

    Tries to proxy Jarvik's model list endpoint. If that fails, falls back to
    the locally allowed models. The returned structure mimics OpenAI's
    ``/v1/models`` response shape.
    """
    url = f"{MODEL_API_BASE}/models"
    headers = {"Authorization": f"Bearer {MODEL_API_KEY}"}
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(url, headers=headers)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, dict) and "data" in data:
                    return data
    except Exception:
        pass
    models = [{"id": m, "object": "model"} for m in sorted(ALLOWED_MODELS)]
    return {"object": "list", "data": models}


# ====== /v1/chat ======
@router.post("/v1/chat")
async def v1_chat(req: ChatReq):
    model = (req.model or MODEL_DEFAULT).strip()
    _validate_model(model)
    data = await _call_model_gateway(
        messages=[m.model_dump() for m in req.messages],
        model=model,
        temperature=req.temperature or 0.5,
    )
    return {
        "answer": _extract_text(data),
        "used_model": model,
        "raw": data,
    }


# ====== /v1/embeddings ======
@router.post("/v1/embeddings")
async def v1_embeddings(payload: dict):
    """Proxy embeddings requests to the model gateway."""
    url = f"{MODEL_API_BASE}/embeddings"
    headers = {
        "Authorization": f"Bearer {MODEL_API_KEY}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as c:
        r = await c.post(url, headers=headers, json=payload)
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail=r.text)
        return r.json()


# ====== /ask (kompatibilní s původním UI) ======
@router.post("/ask")
async def ask(req: AskReq):
    """
    Vstup: { "message": "..." } (+ volitelně model, temperature)
    Výstup: { "response": "..." }  — kompatibilní se starým UI
    """
    model = (req.model or MODEL_DEFAULT).strip()
    _validate_model(model)
    msgs: list[dict] = []
    ctx = await _maybe_context(req.message)
    if ctx:
        ctx_block = "\n\n".join(ctx)
        msgs.append({
            "role": "system",
            "content": f"Relevantní interní kontext (neodhaluj uživateli doslova):\n{ctx_block}"
        })
    msgs.append({"role": "user", "content": req.message})

    data = await _call_model_gateway(
        messages=msgs,
        model=model,
        temperature=req.temperature or 0.5,
    )
    text = _extract_text(data)
    return {"response": text, "used_model": model, "context_used": bool(ctx)}


# ====== Registrace routeru do existující app ======
app.include_router(router)
