from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import json
from pathlib import Path

USERS_FILE = Path(__file__).resolve().parent / "data" / "users.json"

def _load_users():
    if not USERS_FILE.exists():
        return []
    with USERS_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)

def _check_api_key(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Chybí API klíč")

    token = auth.split(" ", 1)[1].strip()
    users = _load_users()

    for u in users:
        if u.get("api_key") == token:
            if not u.get("approved", False):
                raise HTTPException(status_code=403, detail="Účet nebyl schválen")
            return True

    raise HTTPException(status_code=403, detail="Neplatný API klíč")

class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            # povolíme /openapi.json a /docs bez klíče? (necháme zamčené)
            _check_api_key(request)
            return await call_next(request)
        except HTTPException as exc:
            # vrátíme korektní status místo 500
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        except Exception:
            # cokoliv nečekaného -> 500
            return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
