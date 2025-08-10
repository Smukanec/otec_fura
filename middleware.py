from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
USERS_FILE = DATA_DIR / "users.json"

def _load_users():
    if not USERS_FILE.exists():
        return []
    return json.loads(USERS_FILE.read_text(encoding="utf-8"))

class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Allow-list: OPTIONS (CORS preflight) a root
        if request.method == "OPTIONS" or request.url.path == "/":
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Chybí API klíč")

        token = auth.split(" ", 1)[1].strip()
        users = _load_users()

        for u in users:
            if u.get("api_key") == token:
                if not u.get("approved", False):
                    raise HTTPException(status_code=403, detail="Účet není schválen")
                # připoj uživatele do request.state, ať je dostupný v handleru
                request.state.user = u
                return await call_next(request)

        raise HTTPException(status_code=403, detail="Neplatný API klíč")
