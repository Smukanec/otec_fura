sudo tee /home/master/otec_fura/app_ask.py >/dev/null <<'PY'
# -*- coding: utf-8 -*-
import os
from pathlib import Path
from typing import Optional, Dict, Any

import httpx
from fastapi import FastAPI, APIRouter, HTTPException, Header, Depends
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# ==== Konfigurace z ENV ====
MODEL_API_BASE = os.getenv("MODEL_API_BASE", "http://100.115.183.37:8095/v1")
MODEL_API_KEY  = os.getenv("MODEL_API_KEY", "mojelokalnikurvitko")
FURA_API_KEY   = os.getenv("FURA_API_KEY")  # když je nastaven, vyžaduje se X-API-Key

# ==== FastAPI (bez dokumentace) ====
app = FastAPI(
    title="otec-fura",
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json",
)

router = APIRouter()

# ==== UI: cesty a routy ====
WEBUI_DIR = Path(__file__).parent / "webui"
INDEX_HTML = WEBUI_DIR / "index.html"

# (Volitelně) mount na assety, pokud bys měl zvlášť CSS/JS soubory.
# Nepoužíváme /app, ať se to nebije s routou níže.
app.mount("/assets", StaticFiles(directory=str(WEBUI_DIR), html=False), name="assets")

# / -> /app/ (trvalé)
@app.get("/", include_in_schema=False)
async def root_redirect():
    return RedirectResponse(url="/app/", status_code=308)

# /app -> /app/ (kvůli přesnosti s lomítkem)
@app.get("/app", include_in_schema=False)
async def app_redirect():
    return RedirectResponse(url="/app/", status_code=308)

# /app/ -> vrať přímo webui/index.html
@app.get("/app/", include_in_schema=False)
async def app_index():
    if not INDEX_HTML.exists():
        raise HTTPException(404, "UI (webui/index.html) nenalezeno")
    return FileResponse(str(INDEX_HTML), media_type="text/html")

# (volitelná aliasová cesta)
@app.get("/index.html", include_in_schema=False)
async def index_direct():
    return await app_index()

# ==== Zdraví ====
@router.get("/healthz")
async def healthz():
    gw_ok = False
    meta: Dict[str, Any] = {}
    try:
        base = MODEL_API_BASE.rstrip("/")
        url = base[: base.rfind("/")] + "/healthz" if base.endswith("/v1") else base + "/healthz"
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(url)
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

# ==== /v1/chat – kompatibilní s OpenAI style ====
@router.post("/v1/chat", dependencies=[Depends(require_api_key)])
async def v1_chat(body: Dict[str, Any]):
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

# Připojit router
app.include_router(router)
PY

sudo systemctl restart fura-api
