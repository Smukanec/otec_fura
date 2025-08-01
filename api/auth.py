import secrets

def generate_api_key():
    return secrets.token_hex(16)  # např. "a8b7c9e3f1234d..."

# při registraci:
user = {
    "username": "pepa",
    "password_hash": bcrypt.hashpw("heslo".encode(), bcrypt.gensalt()).decode(),
    "api_key": generate_api_key(),
    "approved": False,
    "email": "pepa@example.com",
    "created_at": datetime.utcnow().isoformat()
}
