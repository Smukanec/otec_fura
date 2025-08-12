# middleware.py
import json
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # whitelist cest bez auth
        if request.url.path in ("/", "/openapi.json"):
            return await call_next(request)

        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Chybí API klíč"})

        token = auth.split(" ", 1)[1].strip()

        # načtení uživatelů
        try:
            with open("data/users.json", "r", encoding="utf-8") as f:
                users = json.load(f)
        except Exception:
            return JSONResponse(status_code=500, content={"detail": "Nelze načíst databázi uživatelů"})

        user = next((u for u in users if u.get("api_key") == token and u.get("approved")), None)
        if not user:
            return JSONResponse(status_code=403, content={"detail": "Neplatný API klíč"})

        # povol průchod a předej user do state, kdybys ho chtěl číst v handlerech
        request.state.user = user
        return await call_next(request)
