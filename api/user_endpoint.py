# user_endpoint.py
from fastapi import APIRouter, Request, HTTPException

router = APIRouter()

@router.get("/user")
async def get_user(request: Request):
    current_user = getattr(request.state, "current_user", None)
    # pokud by middleware nebyl u rootu, vrátíme 401 – ale díky middleware se sem bez usera nedostane
    if not current_user:
        raise HTTPException(status_code=401, detail="Neplatný API klíč")
    # nevracej password_hash
    return {
        "username": current_user.get("username"),
        "email": current_user.get("email"),
        "api_key": current_user.get("api_key"),
        "approved": current_user.get("approved"),
        "created_at": current_user.get("created_at"),
    }
