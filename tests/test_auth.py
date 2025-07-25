from fastapi.testclient import TestClient
from main import app
from api import auth

client = TestClient(app)


def test_register_verify_login(tmp_path, monkeypatch):
    users_file = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_FILE", users_file)
    auth.VERIFICATION_CODES.clear()

    resp = client.post(
        "/register",
        json={"username": "bob", "email": "bob@example.com", "password": "secret"},
    )
    assert resp.status_code == 200
    assert "Účet vytvořen" in resp.json().get("message", "")

    code = auth.VERIFICATION_CODES["bob"]
    resp = client.post("/verify", json={"username": "bob", "code": code})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ověřeno"

    resp = client.post("/login", json={"username": "bob", "password": "secret"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "přihlášen"
