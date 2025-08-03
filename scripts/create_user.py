#!/usr/bin/env python3
"""CLI utility to create a new user in data/users.json."""

from __future__ import annotations

import argparse
from datetime import datetime
from getpass import getpass
from pathlib import Path
import sys
import bcrypt

sys.path.append(str(Path(__file__).resolve().parents[1]))
from api.auth import load_users, save_users, generate_api_key


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a new user for Otec Fura")
    parser.add_argument("username", help="Username for the new account")
    parser.add_argument("email", help="Email address for the user")
    parser.add_argument(
        "--approve",
        action="store_true",
        help="Mark the user as approved immediately",
    )
    args = parser.parse_args()

    password = getpass("Password: ")
    confirm = getpass("Confirm password: ")
    if password != confirm:
        raise SystemExit("Passwords do not match")

    users = load_users()
    if any(u["username"] == args.username for u in users):
        raise SystemExit("User already exists")

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user = {
        "username": args.username,
        "password_hash": hashed,
        "email": args.email,
        "api_key": generate_api_key(),
        "approved": bool(args.approve),
        "created_at": datetime.utcnow().isoformat(),
    }
    users.append(user)
    save_users(users)

    print(f"User '{args.username}' created. API key: {user['api_key']}")
    if not args.approve:
        print("The user is not approved yet. Edit data/users.json to approve it.")


if __name__ == "__main__":
    main()
