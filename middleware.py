# middleware.py
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import json
from pathlib import Path

USERS_FILE = Path(__file__).resolve().parent / "data" / "users.json"

def _load_users():
    if not USERS_FILE.exists():
        return []
    with USERS_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)

def _extract_bearer_token(auth_header: str | None) -> str | None:
    if not auth_header:
        return None
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1]

class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, allow_paths: set[str] | None = None):
        super().__init__(app)
        self.allow_paths = allow_paths or set()

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # povolíme jen OpenAPI a root bez klíče (chceš-li je mít zavřené, odeber z allow_paths)
        if path in self.allow_paths:
            return await call_next(request)

        token = _extract_bearer_token(request.headers.get("authorization"))

        if not token:
            raise HTTPException(status_code=401, detail="Chybí API klíč")

        users = _load_users()
        user = next((u for u in users if u.get("api_key") == token), None)

        if not user or not user.get("approved", False):
            raise HTTPException(status_code=403, detail="Neplatný API klíč")

        # Propaguj „aktuálního uživatele“ do request.state, aby si ho endpointy mohly přečíst
        request.state.current_user = user
        return await call_next(request)
