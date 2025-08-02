import sys
import types

# Stub bcrypt to avoid external dependency in tests
bcrypt_stub = types.SimpleNamespace(
    hashpw=lambda password, salt: password,
    gensalt=lambda: b"salt",
    checkpw=lambda password, hashed: password == hashed,
)
sys.modules["bcrypt"] = bcrypt_stub

from fastapi.testclient import TestClient
from main import app
import api.auth as auth
import middleware

client = TestClient(app)

def test_missing_users_file(tmp_path, monkeypatch):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_FILE", users_path)
    monkeypatch.setattr(middleware, "USERS_FILE", users_path)
    assert not users_path.exists()
    resp = client.get("/", headers={"Authorization": "Bearer whatever"})
    assert resp.status_code == 401
    assert users_path.exists()
    assert users_path.read_text() == "[]"
