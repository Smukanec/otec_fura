# middleware.py
import json
from pathlib import Path
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# Path to the JSON database of users. Using a Path relative to this file makes
# the middleware resilient to the current working directory.
USERS_FILE = Path(__file__).resolve().parent / "data" / "users.json"
USERS_FILE.parent.mkdir(parents=True, exist_ok=True)


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, allow_paths: set[str] | None = None):
        super().__init__(app)
        self.allow_paths = allow_paths or set()

    async def dispatch(self, request: Request, call_next):
        # whitelist cest bez auth
        if any(request.url.path.startswith(p) for p in self.allow_paths):
            return await call_next(request)

        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Chybí API klíč"})

        token = auth.split(" ", 1)[1].strip()

        # načtení uživatelů
        try:
            users = json.loads(USERS_FILE.read_text(encoding="utf-8"))
        except FileNotFoundError:
            USERS_FILE.write_text("[]", encoding="utf-8")
            users = []
        except Exception:
            return JSONResponse(status_code=500, content={"detail": "Nelze načíst databázi uživatelů"})

        user = next((u for u in users if u.get("api_key") == token and u.get("approved")), None)
        if not user:
            return JSONResponse(status_code=401, content={"detail": "Neplatný API klíč"})

        # povol průchod a předej user do state, kdybys ho chtěl číst v handlerech
        request.state.current_user = user
        return await call_next(request)
