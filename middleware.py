# middleware.py
import json
from pathlib import Path
from threading import Lock
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# Path to the JSON database of users. Using a Path relative to this file makes
# the middleware resilient to the current working directory.
USERS_FILE = Path(__file__).resolve().parent / "data" / "users.json"
USERS_FILE.parent.mkdir(parents=True, exist_ok=True)

# Cached users and metadata. The cache is refreshed when the underlying
# file changes or when :func:`refresh_users` is called explicitly.
_USERS_CACHE: list[dict] = []
_USERS_MTIME: float | None = None
_USERS_PATH: Path = USERS_FILE
_CACHE_LOCK = Lock()


def refresh_users(force: bool = False) -> list[dict]:
    """Load users from ``USERS_FILE`` if the file changed.

    Parameters
    ----------
    force:
        Reload the file even if the modification time hasn't changed.

    Returns
    -------
    list[dict]
        The in-memory cache of users.
    """

    global _USERS_CACHE, _USERS_MTIME, _USERS_PATH
    with _CACHE_LOCK:
        if _USERS_PATH != USERS_FILE:
            force = True
            _USERS_PATH = USERS_FILE

        try:
            mtime = USERS_FILE.stat().st_mtime
        except FileNotFoundError:
            USERS_FILE.write_text("[]", encoding="utf-8")
            mtime = USERS_FILE.stat().st_mtime

        if force or mtime != _USERS_MTIME:
            try:
                _USERS_CACHE = json.loads(USERS_FILE.read_text(encoding="utf-8"))
            except Exception:
                _USERS_CACHE = []
            _USERS_MTIME = mtime

    return _USERS_CACHE


# Prime the cache on module import.
refresh_users(force=True)


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

        # Načti uživatele z cache – případně ji aktualizuj,
        # pokud se soubor změnil.
        users = refresh_users()

        user = next((u for u in users if u.get("api_key") == token and u.get("approved")), None)
        if not user:
            return JSONResponse(status_code=401, content={"detail": "Neplatný API klíč"})

        # povol průchod a předej user do state, kdybys ho chtěl číst v handlerech
        request.state.current_user = user
        return await call_next(request)
