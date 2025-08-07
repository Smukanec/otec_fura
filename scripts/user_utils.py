import json
from fastapi import Request, HTTPException
from datetime import datetime

USERS_FILE = "data/users.json"

def load_users():
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def get_user_from_token(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Chybí API klíč")
    
    token = auth.split(" ")[1]
    users = load_users()
    
    for user in users:
        if user.get("api_key") == token:
            if not user.get("approved", False):
                raise HTTPException(status_code=403, detail="Účet nebyl schválen")
            return user

    raise HTTPException(status_code=403, detail="Neplatný API klíč")
