from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
import hashlib
import secrets
import json
import os
from pathlib import Path

router = APIRouter()

USERS_FILE = Path(__file__).resolve().parent.parent / "users.json"
VERIFICATION_CODES: dict[str, str] = {}


def load_users() -> dict:
    if USERS_FILE.exists():
        with USERS_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_users(users: dict) -> None:
    with USERS_FILE.open("w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class VerifyRequest(BaseModel):
    username: str
    code: str


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/register")
async def register(data: RegisterRequest):
    users = load_users()
    if data.username in users:
        raise HTTPException(status_code=400, detail="Uživatel již existuje.")

    code = secrets.token_hex(3)
    VERIFICATION_CODES[data.username] = code

    users[data.username] = {
        "email": data.email,
        "password": hash_password(data.password),
        "verified": False,
    }
    save_users(users)

    print(f"[VERIFIKACE] Kód pro {data.username}: {code}")
    return {"status": "ok", "message": "Účet vytvořen. Zadej ověřovací kód."}


@router.post("/verify")
async def verify(data: VerifyRequest):
    users = load_users()
    code = VERIFICATION_CODES.get(data.username)
    if not code or code != data.code:
        raise HTTPException(status_code=401, detail="Neplatný ověřovací kód.")

    users[data.username]["verified"] = True
    save_users(users)
    return {"status": "ověřeno"}


@router.post("/login")
async def login(data: LoginRequest):
    users = load_users()
    user = users.get(data.username)
    if not user:
        raise HTTPException(status_code=404, detail="Uživatel nenalezen.")
    if not user["verified"]:
        raise HTTPException(status_code=403, detail="Uživatel není ověřen.")
    if hash_password(data.password) != user["password"]:
        raise HTTPException(status_code=401, detail="Špatné heslo.")

    return {"status": "přihlášen", "user": data.username}
