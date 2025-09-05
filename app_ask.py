# -*- coding: utf-8 -*-
import os
from typing import Optional, Dict, Any

import httpx
from fastapi import FastAPI, APIRouter, HTTPException, Header, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

# ==== Konfigurace z ENV ====
MODEL_API_BASE = os.getenv("MODEL_API_BASE", "http://100.115.183.37:8095/v1")
MODEL_API_KEY  = os.getenv("MODEL_API_KEY",  "mojelokalnikurvitko")  # klíč do model-gateway
FURA_API_KEY   = os.getenv("FURA_API_KEY")  # pokud nastavíš, bude se vyžadovat X-API-Key

# ==== FastAPI bez Swaggeru (/docs záměrně vypnuto) ====
app = FastAPI(
    title="otec-fura",
    docs_url=None,            # => /docs vrací 404, to je správně
    redoc_url=None,
    openapi_url="/openapi.json",
)

router = APIRouter()

# ==== UI (statické soubory) ====
WEBUI_DIR = os.path.join(os.path.dirname(__file__), "webui")
INDEX_PATH = os.path.join(WEBUI_DIR, "index.html")

# 1) /app/ (funguje i dřívější cesta)
app.mount("/app", StaticFiles(directory=WEBUI_DIR, html=True), name="app")

# 1a) /app (bez lomítka) -> /app/
@router.api_route("/app", methods=["GET", "HEAD"], include_in_schema=False)
async def app_slash_fix():
    return RedirectResponse(url="/app/", status_code=308)

# 2) KOŘEN DOMÉNY "/" -> přímo vrátí index.html (bez přesměrování)
@router.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
async def root_index(request: Request):
    # curl -I (HEAD) má dostat 200 bez těla, prohlížeč (GET) dostane index.html
    if request.method == "HEAD":
        return HTMLResponse("", status_code=200)
    return FileResponse(INDEX_PATH, media_type="text/html")

# ==== /healthz ====
@router.get("/healthz")
async def healthz():
    gw_ok = False
    meta: Dict[str, Any]
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(MODEL_API_BASE.rsplit("/", 1)[0] + "/healthz")
        gw_ok = (r.status_code == 200)
        if r.headers.get("content-type", "").startswith("application/json"):
            meta = r.json()
        else:
            meta = {"raw": r.text}
    except Exception as e:
        meta = {"error": str(e)}

    return {"app": "otec-fura", "ok": True,
            "model_gateway": {"ok": gw_ok, **meta}}

# ==== Ověření X-API-Key (pokud FURA_API_KEY existuje) ====
def require_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    if FURA_API_KEY and x_api_key != FURA_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")

# ==== Jednoduché /ask ====
@router.post("/ask", dependencies=[Depends(require_api_key)])
async def ask(payload: Dict[str, Any]):
    """
    Vstup: {"message":"...", "model":"llama3:8b", "temperature":0.7}
    """
    message = (payload or {}).get("message") or ""
    model   = (payload or {}).get("model")   or "llama3:8b"
    temperature = (payload or {}).get("temperature", 0.7)

    if not message.strip():
        raise HTTPException(400, "Missing 'message'")

    body = {"model": model,
            "messages": [{"role": "user", "content": message}],
            "temperature": temperature}

    headers = {"Content-Type": "application/json",
               "Authorization": f"Bearer {MODEL_API_KEY}"}
    url = (f"{MODEL_API_BASE}/chat/completions"
           if not MODEL_API_BASE.endswith("/chat/completions")
           else MODEL_API_BASE)

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(url, headers=headers, json=body)
    if r.status_code != 200:
        raise HTTPException(r.status_code, r.text)

    data = r.json()
    text = (
        ((data.get("choices") or [{}])[0].get("message") or {}).get("content")
        or data.get("answer")
        or data.get("detail")
        or ""
    )
    return {"response": text}

# ==== OpenAI-like /v1/chat ====
@router.post("/v1/chat", dependencies=[Depends(require_api_key)])
async def v1_chat(body: Dict[str, Any]):
    """
    Pro kompatibilitu: {"model":"...","messages":[...]}
    Vrací: {"answer":"...", "raw":<celá odpověď>}
    """
    if not body or not body.get("messages"):
        raise HTTPException(400, "Missing 'messages'")

    headers = {"Content-Type": "application/json",
               "Authorization": f"Bearer {MODEL_API_KEY}"}
    url = (f"{MODEL_API_BASE}/chat/completions"
           if not MODEL_API_BASE.endswith("/chat/completions")
           else MODEL_API_BASE)

    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(url, headers=headers, json=body)
    if r.status_code != 200:
        raise HTTPException(r.status_code, r.text)

    data = r.json()
    text = (
        ((data.get("choices") or [{}])[0].get("message") or {}).get("content")
        or data.get("answer")
        or data.get("detail")
        or ""
    )
    return {"answer": text, "raw": data}

# připojit router až nakonec
app.include_router(router)
