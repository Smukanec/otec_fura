
import jwt
import datetime
from flask import Blueprint, request, jsonify
from config import SECRET_KEY
import os
import json

auth_router = Blueprint("auth", __name__)

USERS_FILE = "users.json"

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

@auth_router.route("/auth/token", methods=["POST"])
def generate_token():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    users = load_users()
    user = users.get(username)
    if not user or user["password"] != password or not user.get("verified", False):
        return jsonify({"error": "Neplatné přihlášení"}), 403

    token = jwt.encode({
        "username": username,
        "role": user.get("role", "user"),
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=12)
    }, SECRET_KEY, algorithm="HS256")

    return jsonify({"token": token, "user": username})
