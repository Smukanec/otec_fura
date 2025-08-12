# middleware.py
from __future__ import annotations
import os
import json
from typing import Dict, Any
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

USERS_FILE = os.getenv("USERS_FILE", os.path.join(os.path.dirname(__file__), "data", "users.json"))

# Lazy cache {api_key -> user_dict}
_api_key_index: Dict[str, Dict[str, Any]] | None = None

def _load_users_index() -> Dict[str, Dict[str, Any]]:
    global _api_key_index
    if _api_key_index is not None:
        return _api_key_index

    path = USERS_FILE
    if not os.path.isabs(path):
        # běžně /home/master/otec_fura/data/users.json
        path = os.path.join(os.path.dirname(__file__), "data", "users.json")

    if not os.path.exists(path):
        _api_key_index = {}
        return _api_key_index

    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            data = []

    idx: Dict[str, Dict[str, Any]] = {}
    for item in data:
        k = item.get("api_key")
        if k:
            idx[k] = item
    _api_key_index = idx
    return _api_key_index

def _extract_api_key(request: Request) -> str | None:
    # 1) Authorization: Bearer <token>
    auth = request.headers.get("Authorization") or request.headers.get("authorization")
    if auth:
        parts = auth.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
        # fallback: někdo pošle celý token bez "Bearer"
        if len(parts) == 1:
            return parts[0]

    # 2) volitelně ?api_key=... (užitečné při ručním ladění)
    api_key = request.query_params.get("api_key")
    if api_key:
        return api_key

    return None

# cesty, které necháme projít bez tokenu (dokumentace, favicon)
ALLOWLIST = {
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
}

class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # otevřené jen dokumentační cesty; ostatní vyžadují klíč
        if request.url.path in ALLOWLIST:
            return await call_next(request)

        token = _extract_api_key(request)
        if not token:
            # žádný header
            raise HTTPException(status_code=401, detail="Chybí API klíč")

        users = _load_users_index()
        user = users.get(token)
        if not user or not user.get("approved", False):
            # token dorazil, ale uživatel není nebo není schválen
            raise HTTPException(status_code=403, detail="Neplatný API klíč")

        # Propagujme „aktuálního uživatele“ do request.state
        request.state.current_user = user
        return await call_next(request)
