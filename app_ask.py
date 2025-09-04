# -*- coding: utf-8 -*-
import os
from typing import Dict, Any, Optional

import httpx
from fastapi import FastAPI, APIRouter, HTTPException, Header, Depends
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# ==== Konfigurace z ENV ====
MODEL_API_BASE = os.getenv("MODEL_API_BASE", "http://100.115.183.37:8095/v1")
MODEL_API_KEY  = os.getenv("MODEL_API_KEY", "mojelokalnikurvitko")   # klíč pro model-gateway
FURA_API_KEY   = os.getenv("FURA_API_KEY")                           # pokud je nastaven, vyžaduje se X-API-Key

# ==== FastAPI bez /docs a /redoc ====
app = FastAPI(
    title="otec-fura",
    docs_url=None,              # /docs vypnuto (záměrně)
    redoc_url=None,             # /redoc vypnuto
    openapi_url="/openapi.json" # OpenAPI ponecháno (když bys ho chtěl)
)

router = APIRouter()

# ==== Healthz ====
@router.get("/healthz")
async def healthz():
    gw_ok = False
    meta: Dict[str, Any] = {}
    try:
        base = MODEL_API_BASE.rsplit("/", 1)[0] if MODEL_API_BASE.endswith("/v1") else MODEL_API_BASE
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

# ==== Ověření X-API-Key (pokud je nastaven) ====
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
    model = (payload or {}).get("model") or "llama3:8b"
    temperature = (payload or {}).get("temperature", 0.7)

    if not message.strip():
        raise HTTPException(400, "Missing 'message'")

    body = {
        "model": model,
        "messages": [{"role": "user", "content": message}],
        "temperature": temperature,
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {MODEL_API_KEY}"}
    url = f"{MODEL_API_BASE}/chat/completions" if not MODEL_API_BASE.endswith("/chat/completions") else MODEL_API_BASE

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
    Vstup: {"model":"...", "messages":[...]}
    Výstup: {"answer":"...", "raw":<celá odpověď gateway>}
    """
    if not body or not body.get("messages"):
        raise HTTPException(400, "Missing 'messages'")

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {MODEL_API_KEY}"}
    url = f"{MODEL_API_BASE}/chat/completions" if not MODEL_API_BASE.endswith("/chat/completions") else MODEL_API_BASE

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

# ==== API router ====
app.include_router(router)

# ==== UI (statika) ====
WEBUI_DIR = os.path.join(os.path.dirname(__file__), "webui")

# 1) UI na kořeni "/" – StaticFiles umístíme AŽ PO include_router,
#    aby /healthz, /ask, /v1/chat nebyly přestřelené statikou.
app.mount("/", StaticFiles(directory=WEBUI_DIR, html=True), name="root-ui")

# 2) Zpětná kompatibilita: /app a /app/ přesměruj na "/"
@app.get("/app", include_in_schema=False)
async def app_alias_no_slash():
    return RedirectResponse(url="/", status_code=308)

@app.get("/app/", include_in_schema=False)
async def app_alias_slash():
    return RedirectResponse(url="/", status_code=308)
