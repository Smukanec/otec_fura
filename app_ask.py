import os
import urllib.parse
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel
from starlette.responses import RedirectResponse, HTMLResponse
from starlette.staticfiles import StaticFiles

# Původní FURA aplikace (auth/knowledge/api atd.) – přimontujeme ji pod /core
from main import app as core_app

# === Konfigurace z ENV ========================================================
MODEL_API_BASE = os.getenv("MODEL_API_BASE", "http://100.115.183.37:8095/v1").rstrip("/")
MODEL_API_KEY  = (os.getenv("MODEL_API_KEY") or "").strip() or None
MODEL_DEFAULT  = os.getenv("MODEL_DEFAULT", "llama3:8b").strip()
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "120"))
FURA_API_KEY   = (os.getenv("FURA_API_KEY") or "").strip()

# CSV whitelist modelů (volitelné). Když je neprázdný, kontrolujeme modely proti němu.
MODEL_ALLOWED = [m.strip() for m in (os.getenv("MODEL_ALLOWED") or "").split(",") if m.strip()]

# Zap/vyp RAG kontext pro /ask (default: zapnuto)
USE_CONTEXT_DEFAULT = (os.getenv("USE_CONTEXT_DEFAULT", "true").lower() in ("1", "true", "yes"))

# Cesta k web UI (statické soubory)
WEBUI_DIR = os.getenv("FURA_WEBUI_DIR", os.path.join(os.path.dirname(__file__), "webui"))

# === Wrapper FastAPI aplikace (veřejná vrstva) ===============================
app = FastAPI(title="Otec FURA — wrapper")
router = APIRouter()


# === Autorizační závislost (jen když je FURA_API_KEY nastaven) ===============
def api_auth(authorization: Optional[str] = Header(None),
             x_api_key: Optional[str] = Header(None)) -> None:
    if not FURA_API_KEY:
        return  # auth vypnuta
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not token and x_api_key:
        token = x_api_key.strip()
    if token != FURA_API_KEY:
        raise HTTPException(status_code=401, detail="Chybí API klíč")


# === Datové modely ===========================================================
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
    use_context: Optional[bool] = None  # None => použij USE_CONTEXT_DEFAULT


# === Pomocné funkce ==========================================================
def _headers_upstream() -> dict:
    h = {"Content-Type": "application/json"}
    if MODEL_API_KEY:
        h["Authorization"] = f"Bearer {MODEL_API_KEY}"
    return h


def _validate_model(name: str) -> str:
    model = (name or MODEL_DEFAULT).strip()
    if MODEL_ALLOWED and model not in MODEL_ALLOWED:
        raise HTTPException(status_code=400, detail=f"Model '{model}' není povolen")
    return model


async def _call_chat_completions(payload: dict) -> dict:
    url = f"{MODEL_API_BASE}/chat/completions"
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as c:
        r = await c.post(url, headers=_headers_upstream(), json=payload)
        if r.status_code >= 400:
            try:
                detail = r.json()
            except Exception:
                detail = {"detail": r.text}
            raise HTTPException(status_code=r.status_code, detail=detail)
        return r.json()


async def _maybe_context(query: str) -> list[str]:
    """Zkusí zavolat původní /get_context na přimountované /core; pokud selže, vrátí []."""
    if not query:
        return []
    ctx: list[str] = []
    # 1) GET varianta
    try:
        get_url = f"http://127.0.0.1:8090/core/get_context?query={urllib.parse.quote(query)}"
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
    # 2) POST fallback
    if not ctx:
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.post("http://127.0.0.1:8090/core/get_context",
                                 json={"query": query, "top_k": 4})
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


def _extract_text(openai_like: dict) -> str:
    try:
        return openai_like.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
    except Exception:
        return ""


# === Veřejné endpointy (bez auth, pokud FURA_API_KEY prázdné) ================
@app.get("/healthz")
async def healthz():
    return {
        "name": "otec-fura",
        "ui": True,
        "ask": True,
        "v1chat": True,
        "model_api_base": MODEL_API_BASE,
        "require_api_key": bool(FURA_API_KEY),
        "default_model": MODEL_DEFAULT,
        "allowed_models": MODEL_ALLOWED or None,
    }


@app.get("/auth/config")
async def auth_config():
    return {
        "require_api_key": bool(FURA_API_KEY),
        "default_model": MODEL_DEFAULT,
        "allowed_models": MODEL_ALLOWED or None,
    }


@app.get("/v1/models")
async def v1_models():
    return {
        "object": "list",
        "data": [{"id": m, "object": "model"} for m in (MODEL_ALLOWED or [MODEL_DEFAULT])],
    }


@router.post("/v1/chat")
async def v1_chat(req: ChatReq, _=Depends(api_auth)):
    model = _validate_model(req.model or MODEL_DEFAULT)
    payload = {
        "model": model,
        "messages": [m.model_dump() for m in req.messages],
        "temperature": req.temperature,
    }
    data = await _call_chat_completions(payload)
    return {"answer": _extract_text(data), "upstream": data, "model": model}


@router.post("/ask")
async def ask(req: AskReq, _=Depends(api_auth)):
    model = _validate_model(req.model or MODEL_DEFAULT)
    use_ctx = USE_CONTEXT_DEFAULT if req.use_context is None else bool(req.use_context)
    messages: list[dict] = []
    if use_ctx:
        ctx = await _maybe_context(req.message)
        if ctx:
            messages.append({"role": "system",
                             "content": "Relevantní kontext (neodhaluj doslova):\n" + "\n\n".join(ctx)})
    messages.append({"role": "user", "content": req.message})
    data = await _call_chat_completions({"model": model, "messages": messages,
                                         "temperature": req.temperature})
    return {"response": _extract_text(data), "model": model, "context_used": use_ctx}


# Zaregistruj router s /v1/chat a /ask
app.include_router(router)

# Statické UI na /app (bez auth)
if os.path.isdir(WEBUI_DIR):
    app.mount("/app", StaticFiles(directory=WEBUI_DIR, html=True), name="webui")
else:
    @app.get("/app")
    async def app_fallback():
        return HTMLResponse("<h1>Otec FURA UI</h1><p>UI není nainstalované.</p>")

# Redirect kořen → /app/
@app.get("/")
async def _root():
    return RedirectResponse(url="/app/")

# Původní FURA aplikaci přimontujeme na /core (tam ať si řeší své auth)
app.mount("/core", core_app)
