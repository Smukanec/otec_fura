import json
import os
import subprocess
import sys
from pathlib import Path


def test_create_user_script(tmp_path):
    root = Path(__file__).resolve().parents[1]
    users_file = tmp_path / "users.json"
    sitecustomize = tmp_path / "sitecustomize.py"
    sitecustomize.write_text(
        f"""
import sys, types, getpass
from pathlib import Path

bcrypt_stub = types.SimpleNamespace(
    hashpw=lambda password, salt: b"hashed_" + password,
    gensalt=lambda: b"salt",
)
sys.modules['bcrypt'] = bcrypt_stub
getpass.getpass = lambda prompt='', stream=None: 'secret'
import api.auth as auth
old_file = auth.USERS_FILE
auth.USERS_FILE = Path(r"{users_file}")
auth.USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
auth.USERS_FILE.write_text("[]")
if old_file.exists():
    old_file.unlink()
    if not any(old_file.parent.iterdir()):
        old_file.parent.rmdir()
"""
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{root}:{tmp_path}"
    subprocess.run(
        [sys.executable, str(root / "scripts" / "create_user.py")],
        input="alice\nalice@example.com\n",
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )
    data = json.loads(users_file.read_text())
    assert len(data) == 1
    user = data[0]
    assert user["username"] == "alice"
    assert user["email"] == "alice@example.com"
    assert user["password_hash"] != "secret"
    assert user["password_hash"].startswith("hashed_")
