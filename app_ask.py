import os
from typing import Any, Dict, List, Optional

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.routing import APIRouter
from pydantic import BaseModel
from starlette.responses import JSONResponse, RedirectResponse
from starlette.staticfiles import StaticFiles

# ===== config z ENV =====
MODEL_API_BASE = os.getenv("MODEL_API_BASE", "http://100.115.183.37:8095/v1")
MODEL_API_KEY = os.getenv("MODEL_API_KEY", "")
FURA_API_KEY   = os.getenv("FURA_API_KEY", "")  # nepovinné – pokud je, vyžadujeme X-API-Key

app = FastAPI(title="Otec Fura", version="1.0.0")
router = APIRouter()


# ===== API-key ochrana (volitelné) =====
def require_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    if not FURA_API_KEY:  # žádná ochrana
        return True
    if x_api_key != FURA_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


# ===== UI / statika =====
@app.get("/", include_in_schema=False)
async def root_redirect():
    # root -> /app/ (aby se servíroval webui/index.html)
    return RedirectResponse(url="/app/", status_code=308)

# montujeme webui/ jako UI
app.mount(
    "/app",
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "webui"), html=True),
    name="app",
)


# ===== model gateway volání =====
class AskReq(BaseModel):
    message: str
    model: str


@router.get("/healthz")
async def healthz():
    # pokusíme se sáhnout na model gateway /healthz (nevadí, když spadne)
    info: Dict[str, Any] = {"app": "otec-fura", "ok": True}
    try:
        url = MODEL_API_BASE.rstrip("/").rsplit("/", 1)[0] + "/healthz"
        headers = {"Authorization": f"Bearer {MODEL_API_KEY}"} if MODEL_API_KEY else {}
        async with httpx.AsyncClient(timeout=5) as cli:
            r = await cli.get(url, headers=headers)
            r.raise_for_status()
            info["model_gateway"] = r.json()
    except Exception:
        info["model_gateway"] = {"ok": False}
    return JSONResponse(info)


@router.post("/ask", dependencies=[Depends(require_api_key)])
async def ask(req: AskReq):
    """Jednoduché volání – pošle prompt do modelu a vrátí text."""
    payload = {
        "model": req.model,
        "messages": [{"role": "user", "content": req.message}],
    }
    headers = {"Content-Type": "application/json"}
    if MODEL_API_KEY:
        headers["Authorization"] = f"Bearer {MODEL_API_KEY}"

    async with httpx.AsyncClient(timeout=60) as cli:
        r = await cli.post(f"{MODEL_API_BASE.rstrip('/')}/chat/completions", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()

    # tolerantní extrakce textu
    text = (
        (data.get("choices") or [{}])[0].get("message", {}).get("content")
        or data.get("answer")
        or data.get("detail")
        or ""
    )
    return {"response": text, "raw": data}


# OpenAI-like JSON proxy: POST /v1/chat  ->  .../chat/completions
@router.post("/v1/chat", dependencies=[Depends(require_api_key)])
async def v1_chat(body: Dict[str, Any]):
    headers = {"Content-Type": "application/json"}
    if MODEL_API_KEY:
        headers["Authorization"] = f"Bearer {MODEL_API_KEY}"
    async with httpx.AsyncClient(timeout=120) as cli:
        r = await cli.post(f"{MODEL_API_BASE.rstrip('/')}/chat/completions", json=body, headers=headers)
        r.raise_for_status()
        data = r.json()

    # přidejme i pohodlné pole "answer"
    answer = (
        (data.get("choices") or [{}])[0].get("message", {}).get("content")
        or data.get("answer")
        or data.get("detail")
        or ""
    )
    return {"answer": answer, "raw": data}


app.include_router(router)
