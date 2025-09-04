import os
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from starlette.responses import HTMLResponse, PlainTextResponse
from starlette.staticfiles import StaticFiles

# 1) Vezmeme jádro aplikace (tvoje původní API a RAG)
from main import app as core_app

app = core_app
router = APIRouter()

# 2) Konfigurace model gateway (Jarvik01)
MODEL_API_BASE = os.getenv("MODEL_API_BASE", "http://100.115.183.37:8095/v1").rstrip("/")
MODEL_API_KEY  = os.getenv("MODEL_API_KEY",  "mojelokalnikurvitko")
MODEL_DEFAULT  = os.getenv("MODEL_DEFAULT",  "llama3:8b")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "120"))

# Volitelná ochrana API klíčem pro FURU; pokud není nastaveno, nevyžaduje se
FURA_API_KEY = os.getenv("FURA_API_KEY", "").strip()

WEBUI_DIR = os.path.join(os.path.dirname(__file__), "webui")


def require_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> bool:
    """Pokud je nastaven FURA_API_KEY, endpointy /ask a /v1/chat vyžadují shodu v hlavičce X-API-Key."""
    if FURA_API_KEY and x_api_key != FURA_API_KEY:
        raise HTTPException(status_code=401, detail="Chybí API klíč")
    return True


# 3) Odstraníme defaultní "/" route(y) z původního appu (ta tě přesměrovávala na /docs)
def _remove_routes(paths_to_remove: set[str]) -> None:
    kept = []
    for r in app.router.routes:
        path = getattr(r, "path", None) or getattr(r, "path_format", None)
        if path in paths_to_remove:
            continue
        kept.append(r)
    app.router.routes = kept

_remove_routes({"/"})  # zruš starý root (necháváme /docs i /redoc být)


# 4) UI – statika na /app (zůstává) + UI přímo na root "/"
if os.path.isdir(WEBUI_DIR):
    app.mount("/app", StaticFiles(directory=WEBUI_DIR, html=True), name="webui")


@app.get("/", include_in_schema=False)
async def root_index():
    """Holá adresa -> přímo načte webui/index.html (bez přesměrování na /app ani /docs)."""
    index_path = os.path.join(WEBUI_DIR, "index.html")
    if os.path.isfile(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return PlainTextResponse("UI není nahrané (chybí webui/index.html).", status_code=200)


# 5) Health
@app.get("/healthz", include_in_schema=False)
async def healthz():
    gw = {}
    ok = True
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(MODEL_API_BASE.replace("/v1", "") + "/healthz")
            gw = r.json()
    except Exception:
        ok = False
    return {"app": "otec-fura", "ok": ok, "model_gateway": {**gw, "ok": gw.get("ollama_ok", False)}}


# 6) Model rozhraní
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatReq(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    temperature: Optional[float] = None


class AskReq(BaseModel):
    message: str
    model: Optional[str] = None
    temperature: Optional[float] = None


@router.post("/v1/chat")
async def v1_chat(req: ChatReq, _: bool = Depends(require_api_key)):
    payload = {
        "model": req.model or MODEL_DEFAULT,
        "messages": [m.model_dump() for m in req.messages],
    }
    if req.temperature is not None:
        payload["temperature"] = req.temperature

    headers = {"Authorization": f"Bearer {MODEL_API_KEY}"}
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        r = await client.post(f"{MODEL_API_BASE}/chat/completions", json=payload, headers=headers)

    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Model gateway error: {r.text}")

    data = r.json()
    msg = (((data.get("choices") or [{}])[0]).get("message") or {}).get("content")
    return {"answer": msg, "raw": data}


@router.post("/ask")
async def ask(req: AskReq, _: bool = Depends(require_api_key)):
    chat = ChatReq(messages=[ChatMessage(role="user", content=req.message)],
                   model=req.model, temperature=req.temperature)
    res = await v1_chat(chat)  # type: ignore
    return {"response": res["answer"]}


# 7) Zaregistruj router (přidá /ask a /v1/chat)
app.include_router(router)
