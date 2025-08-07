from fastapi import APIRouter, Request
from scripts.user_utils import get_user_from_token

router = APIRouter()

@router.get("/user")
async def get_user(request: Request):
    user = get_user_from_token(request)
    if not user:
        return {"error": "Unauthorized"}
    return user
