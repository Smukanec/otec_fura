from fastapi import APIRouter, Request
import sys
import os

sys.path.append(os.path.abspath("scripts"))

from user_utils import get_user_from_token

router = APIRouter()

@router.get("/user")
async def get_user(request: Request):
    user = get_user_from_token(request)
    return {
        "username": user["username"],
        "model": user.get("model", "nezadán")
    }
