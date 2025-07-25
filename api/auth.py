from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
import hashlib, secrets, json, os

router = APIRouter()

USERS_FILE = "users.json"
VERIFICATION_CODES = {}

# ---------- Pomocné funkce ----------

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# ---------- Datové modely ----------

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

# ---------- Endpointy ----------

@router.post("/register")
def register(req: RegisterRequest):
    users = load_users()
    if req.username in users:
        raise HTTPException(status_code=400, detail="Uživatel už existuje")
    
    code = secrets.token_hex(3)
    VERIFICATION_CODES[req.username] = code

    users[req.username] = {
        "email": req.email,
        "password_hash": hash_password(req.password),
        "verified": False,
    }
    save_users(users)
    print(f"[INFO] Ověřovací kód pro {req.username}: {code}")
    return {"status": "registered", "message": "Zadej ověřovací kód, který ti byl vygenerován."}

@router.post("/verify")
def verify(req: VerifyRequest):
    users = load_users()
    if req.username not in users:
        raise HTTPException(status_code=404, detail="Uživatel neexistuje")

    if VERIFICATION_CODES.get(req.username) != req.code:
        raise HTTPException(status_code=400, detail="Neplatný ověřovací kód")

    users[req.username]["verified"] = True
    save_users(users)
    return {"status": "verified"}

@router.post("/login")
def login(req: LoginRequest):
    users = load_users()
    user = users.get(req.username)

    if not user or user["password_hash"] != hash_password(req.password):
        raise HTTPException(status_code=401, detail="Špatné přihlašovací údaje")
    if not user["verified"]:
        raise HTTPException(status_code=403, detail="Uživatel není ověřen")

    return {"status": "přihlášen"}
