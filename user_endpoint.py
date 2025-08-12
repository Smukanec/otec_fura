# user_endpoint.py
from fastapi import APIRouter, Request

router = APIRouter()

@router.get("/user")
async def get_user(request: Request):
    u = getattr(request.state, "current_user", None)
    # pokud by middleware nebyl u rootu, vrátíme 401/403 – ale díky middleware se sem bez usera nedostane
    if not u:
        return {"detail": "Neplatný API klíč"}
    # nevracej password_hash
    return {
        "username": u.get("username"),
        "email": u.get("email"),
        "api_key": u.get("api_key"),
        "approved": u.get("approved"),
        "created_at": u.get("created_at"),
    }
