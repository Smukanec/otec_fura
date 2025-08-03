# middleware.py – Zajišťuje kontrolu API klíče pro každý požadavek

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import json
from pathlib import Path

USERS_FILE = Path(__file__).resolve().parent / "data/users.json"


def load_users():
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not USERS_FILE.exists():
        USERS_FILE.write_text("[]")
    return json.loads(USERS_FILE.read_text())

def get_user_by_apikey(api_key: str):
    users = load_users()
    for user in users:
        if user["api_key"] == api_key:
            return user
    return None

class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Výjimka: nepoužívej kontrolu na tyto cesty
        if request.url.path.startswith("/auth"):
            return await call_next(request)

        auth = request.headers.get("Authorization")
        if not auth or not auth.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Chybí API klíč")

        api_key = auth.replace("Bearer ", "")
        user = get_user_by_apikey(api_key)
        if not user:
            raise HTTPException(status_code=401, detail="Neplatný API klíč")

        if not user.get("approved", False):
            raise HTTPException(status_code=403, detail="Účet není schválen")

        request.state.user = user  # může se hodit v dalších funkcích
        return await call_next(request)
