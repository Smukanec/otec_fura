# -*- coding: utf-8 -*-
import os
from typing import Optional, Dict, Any

import httpx
from fastapi import FastAPI, APIRouter, HTTPException, Header, Depends
from fastapi.responses import RedirectResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles

# ==== Konfigurace z ENV ====
MODEL_API_BASE = os.getenv("MODEL_API_BASE", "http://100.115.183.37:8095/v1")
MODEL_API_KEY  = os.getenv("MODEL_API_KEY", "mojelokalnikurvitko")
FURA_API_KEY   = os.getenv("FURA_API_KEY")

# ==== FastAPI bez /docs a /redoc ====
app = FastAPI(
    title="otec-fura",
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json",
)
router = APIRouter()

# ==== UI (StaticFiles) ====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEBUI_DIR = os.path.join(BASE_DIR, "webui")
index_path = os.path.join(WEBUI_DIR, "index.html")

if not os.path.isdir(WEBUI_DIR):
    print(f"[FURA-UI] WARNING: WEBUI_DIR neexistuje: {WEBUI_DIR}")
elif not os.path.isfile(index_path):
    print(f"[FURA-UI] WARNING: Chybí index.html: {index_path}")
else:
    print(f"[FURA-UI] UI mount OK: {WEBUI_DIR} (index: {index_path})")

# StaticFiles mount
app.mount("/app", StaticFiles(directory=WEBUI_DIR, html=True), name="ui")

# >>> Toto je důležité: obsluha GET /app/ <<<
@router.get("/app/", include_in_schema=False)
async def app_index():
    return FileResponse(index_path, media_type="text/html")

# / -> 308 redirect na /app/
@router.get("/", include_in_schema=False)
async def root_redirect_get():
    return RedirectResponse(url="/app/", status_code=308)

@router.head("/", include_in_schema=False)
async def root_redirect_head():
    return Response(status_code=308, headers={"Location": "/app/"})

# Volitelně přímý náhled
@router.get("/index.html", include_in_schema=False)
async def index_direct():
    return FileResponse(index_path, media_type="text/html")

# ==== healthz ====
@router.get("/healthz")
async def healthz():
    gw_ok = False
    meta: Dict[str, Any] = {}
    try:
        base = MODEL_API_BASE.rstrip("/")
        root = base[: base.rfind("/")] if base.endswith("/chat") or base.endswith("/chat/completions") else base
        url  = f"{root}/healthz"
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

# ==== auth ====
def require_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    if FURA_API_KEY and x_api_key != FURA_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")

# ==== /ask ====
@router.post("/ask", dependencies=[Depends(require_api_key)])
async def ask(payload: Dict[str, Any]):
    message = (payload or {}).get("message") or ""
    model   = (payload or {}).get("model") or "llama3:8b"
    temperature = (payload or {}).get("temperature", 0.7)

    if not message.strip():
        raise HTTPException(400, "Missing 'message'")

    body = {"model": model, "messages": [{"role": "user", "content": message}], "temperature": temperature}
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {MODEL_API_KEY}"}
    url = MODEL_API_BASE
    if not url.endswith("/chat/completions"):
        url = f"{url.rstrip('/')}/chat/completions"

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(url, headers=headers, json=body)
    if r.status_code != 200:
        raise HTTPException(r.status_code, r.text)

    data = r.json()
    text = (((data.get("choices") or [{}])[0].get("message") or {}).get("content")
            or data.get("answer") or data.get("detail") or "")
    return {"response": text}

# ==== /v1/chat ====
@router.post("/v1/chat", dependencies=[Depends(require_api_key)])
async def v1_chat(body: Dict[str, Any]):
    if not body or not body.get("messages"):
        raise HTTPException(400, "Missing 'messages'")

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {MODEL_API_KEY}"}
    url = MODEL_API_BASE
    if not url.endswith("/chat/completions"):
        url = f"{url.rstrip('/')}/chat/completions"

    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(url, headers=headers, json=body)
    if r.status_code != 200:
        raise HTTPException(r.status_code, r.text)

    data = r.json()
    text = (((data.get("choices") or [{}])[0].get("message") or {}).get("content")
            or data.get("answer") or data.get("detail") or "")
    return {"answer": text, "raw": data}

# Připojit router
app.include_router(router)
