# auth.py – Registrace a přihlašování s generováním API klíče

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import bcrypt
import secrets
import json
from pathlib import Path
from datetime import datetime

router = APIRouter()
USERS_FILE = Path("data/users.json")

# Vytvoř složku data, pokud neexistuje
USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
if not USERS_FILE.exists():
    USERS_FILE.write_text("[]")

# Datové modely
class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str

class LoginRequest(BaseModel):
    username: str
    password: str

# Helper funkce
def load_users():
    return json.loads(USERS_FILE.read_text())

def save_users(users):
    USERS_FILE.write_text(json.dumps(users, indent=2))

def get_user_by_apikey(api_key: str):
    users = load_users()
    for user in users:
        if user["api_key"] == api_key:
            return user
    return None

def generate_api_key():
    return secrets.token_hex(16)  # např. "a8b7c9e3f1234d..."

# Endpoint pro registraci
@router.post("/auth/register")
def register(data: RegisterRequest):
    users = load_users()
    if any(u["username"] == data.username for u in users):
        raise HTTPException(status_code=400, detail="Uživatel už existuje")

    hashed = bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode()
    user = {
        "username": data.username,
        "password_hash": hashed,
        "email": data.email,
        "api_key": generate_api_key(),
        "approved": False,
        "created_at": datetime.utcnow().isoformat()
    }
    users.append(user)
    save_users(users)
    return {"message": "Registrace úspěšná. API klíč obdržíte po schválení administrátorem."}

# Endpoint pro přihlášení – vrátí API klíč
@router.post("/auth/token")
def login(data: LoginRequest):
    users = load_users()
    user = next((u for u in users if u["username"] == data.username), None)
    if not user:
        raise HTTPException(status_code=401, detail="Neplatné jméno")

    if not bcrypt.checkpw(data.password.encode(), user["password_hash"].encode()):
        raise HTTPException(status_code=401, detail="Neplatné heslo")

    if not user.get("approved", False):
        raise HTTPException(status_code=403, detail="Účet čeká na schválení")

    return {"api_key": user["api_key"]}

# Endpoint pro zjištění informací o uživateli podle API klíče
@router.get("/auth/me")
def auth_me(request: Request):
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Chybí API klíč")

    api_key = auth.replace("Bearer ", "")
    user = get_user_by_apikey(api_key)
    if not user:
        raise HTTPException(status_code=401, detail="Neplatný API klíč")

    return {
        "username": user["username"],
        "email": user["email"],
        "approved": user.get("approved", False),
    }
