# -*- coding: utf-8 -*-
import os
from typing import Optional, Dict, Any

import httpx
from fastapi import FastAPI, APIRouter, HTTPException, Header, Depends
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# ==== Konfigurace z ENV ====
MODEL_API_BASE = os.getenv("MODEL_API_BASE", "http://100.115.183.37:8095/v1")
MODEL_API_KEY  = os.getenv("MODEL_API_KEY", "mojelokalnikurvitko")  # klíč do model-gateway
FURA_API_KEY   = os.getenv("FURA_API_KEY")  # pokud nastavíš, bude se vyžadovat X-API-Key

# ==== FastAPI bez /docs a /redoc (API je čisté, UI servírujeme sami) ====
app = FastAPI(
    title="otec-fura",
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json",
)

router = APIRouter()

# ==== UI (statika) ====
WEBUI_DIR = os.path.join(os.path.dirname(__file__), "webui")

# 1) Redirect root -> /app/ (GET i HEAD kvůli curl -I)
@router.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
async def root_redirect():
    return RedirectResponse(url="/app/", status_code=308)

# 2) Redirect /app -> /app/ (GET i HEAD), abychom eliminovali 404 bez lomítka
@router.api_route("/app", methods=["GET", "HEAD"], include_in_schema=False)
async def app_redirect():
    return RedirectResponse(url="/app/", status_code=308)

# 3) /app/ – vlastní UI ze složky webui (index.html)
#    POZOR: StaticFiles na mountu vyžaduje /app/ (s lomítkem),
#    /app bez lomítka jsme ošetřili routou výše.
app.mount("/app", StaticFiles(directory=WEBUI_DIR, html=True), name="app")

# (volitelné) přímý přístup na /index.html, když bys chtěl obejít mount
@router.get("/index.html", include_in_schema=False)
async def index_direct():
    return FileResponse(os.path.join(WEBUI_DIR, "index.html"), media_type="text/html")

# ==== /healthz ====
@router.get("/healthz")
async def healthz():
    gw_ok = False
    meta: Dict[str, Any]
    try:
        base = MODEL_API_BASE.rsplit("/", 1)[0]  # .../v1 -> ...
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{base}/healthz")
        gw_ok = (r.status_code == 200)
        if r.headers.get("content-type", "").startswith("application/json"):
            meta = r.json()
        else:
            meta = {"raw": r.text}
    except Exception as e:
        meta = {"error": str(e)}

    return {"app": "otec-fura", "ok": True, "model_gateway": {"ok": gw_ok, **meta}}

# ==== Ověření X-API-Key (pokud je nastaven FURA_API_KEY) ====
def require_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    if FURA_API_KEY and x_api_key != FURA_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")

# ==== /ask – jednoduché volání ====
@router.post("/ask", dependencies=[Depends(require_api_key)])
async def ask(payload: Dict[str, Any]):
    """
    Vstup: {"message": "...", "model": "llama3:8b", "temperature": 0.7}
    """
    message = (payload or {}).get("message") or ""
    model   = (payload or {}).get("model")   or "llama3:8b"
    temperature = (payload or {}).get("temperature", 0.7)

    if not message.strip():
        raise HTTPException(400, "Missing 'message'")

    body = {"model": model, "messages": [{"role": "user", "content": message}], "temperature": temperature}
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {MODEL_API_KEY}"}
    url = MODEL_API_BASE if MODEL_API_BASE.endswith("/chat/completions") else f"{MODEL_API_BASE}/chat/completions"

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

# ==== /v1/chat – OpenAI‑like ====
@router.post("/v1/chat", dependencies=[Depends(require_api_key)])
async def v1_chat(body: Dict[str, Any]):
    if not body or not body.get("messages"):
        raise HTTPException(400, "Missing 'messages'")

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {MODEL_API_KEY}"}
    url = MODEL_API_BASE if MODEL_API_BASE.endswith("/chat/completions") else f"{MODEL_API_BASE}/chat/completions"

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

# Připojit router nakonec, ať je pořadí jasné (redirecty přidané dřív platí).
app.include_router(router)
