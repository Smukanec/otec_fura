# admin_tools.py – nástroj pro správu uživatelů

import json
from pathlib import Path
import sys

USERS_FILE = Path("data/users.json")

# Načti uživatele
def load_users():
    return json.loads(USERS_FILE.read_text())

def save_users(users):
    USERS_FILE.write_text(json.dumps(users, indent=2))

# Seznam všech uživatelů
def list_users():
    users = load_users()
    for user in users:
        print(f"{user['username']} | approved: {user['approved']} | email: {user.get('email', '-')}")

# Schválit uživatele
def approve_user(username):
    users = load_users()
    for user in users:
        if user['username'] == username:
            user['approved'] = True
            save_users(users)
            print(f"✅ Uživatel '{username}' byl schválen.")
            return
    print(f"❌ Uživatel '{username}' nenalezen.")

# Zobrazit API klíč
def show_apikey(username):
    users = load_users()
    for user in users:
        if user['username'] == username:
            print(f"🔑 API klíč pro {username}: {user['api_key']}")
            return
    print(f"❌ Uživatel '{username}' nenalezen.")

# CLI ovládání
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Použití: python admin_tools.py [list | approve <jméno> | show <jméno>]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "list":
        list_users()
    elif cmd == "approve" and len(sys.argv) == 3:
        approve_user(sys.argv[2])
    elif cmd == "show" and len(sys.argv) == 3:
        show_apikey(sys.argv[2])
    else:
        print("Neplatný příkaz.")
