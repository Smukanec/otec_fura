from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import json
import os
from hashlib import sha256

router = APIRouter()

USERS_FILE = "users.json"

class UserRegister(BaseModel):
    username: str
    password: str
    email: str

class UserLogin(BaseModel):
    username: str
    password: str

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)

def hash_password(password: str) -> str:
    return sha256(password.encode()).hexdigest()

@router.post("/auth/register")
def register(user: UserRegister):
    users = load_users()
    if user.username in users:
        raise HTTPException(status_code=400, detail="Uživatel už existuje.")
    users[user.username] = {
        "password": hash_password(user.password),
        "email": user.email
    }
    save_users(users)
    return {"message": f"Uživatel {user.username} úspěšně zaregistrován."}

@router.post("/auth/token")
def login(user: UserLogin):
    users = load_users()
    if user.username not in users:
        raise HTTPException(status_code=401, detail="Neplatné přihlašovací údaje.")
    hashed = hash_password(user.password)
    if users[user.username]["password"] != hashed:
        raise HTTPException(status_code=401, detail="Neplatné heslo.")
    return {"token": f"fake-token-{user.username}"}
