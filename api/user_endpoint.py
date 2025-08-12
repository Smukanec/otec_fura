# user_endpoint.py
from fastapi import APIRouter, Request, HTTPException

router = APIRouter()

@router.get("/user")
async def get_user(request: Request):
    # middleware už ověřil klíč a uložil current_user
    user = getattr(request.state, "current_user", None)
    if not user:
        # Teoreticky by se to stát nemělo – jen pojistka.
        raise HTTPException(status_code=403, detail="Neplatný API klíč")
    # neposíláme password_hash
    return {
        "username": user.get("username"),
        "email": user.get("email"),
        "api_key": user.get("api_key"),
        "approved": user.get("approved"),
        "created_at": user.get("created_at"),
    }
