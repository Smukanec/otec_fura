import sys
import types
import asyncio
import json
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

# Stub bcrypt to avoid external dependency in tests
bcrypt_stub = types.SimpleNamespace(
    hashpw=lambda password, salt: password,
    gensalt=lambda: b"salt",
    checkpw=lambda password, hashed: password == hashed,
)
sys.modules["bcrypt"] = bcrypt_stub

from fastapi import HTTPException
from main import app
import api.auth as auth
import middleware


class SimpleResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return json.loads(self._body.decode())


class SimpleClient:
    def __init__(self, app):
        self.app = app

    def _request(self, method, path, json_body=None, headers=None):
        headers = headers or {}
        body_bytes = b""
        header_list = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
        if json_body is not None:
            body_bytes = json.dumps(json_body).encode()
            header_list.append((b"content-type", b"application/json"))
            header_list.append((b"content-length", str(len(body_bytes)).encode()))
        else:
            header_list.append((b"content-length", b"0"))

        scope = {
            "type": "http",
            "asgi": {"spec_version": "2.1", "version": "3.0"},
            "method": method,
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": header_list,
            "client": ("test", 123),
            "server": ("testserver", 80),
            "scheme": "http",
        }

        messages = []

        async def receive():
            nonlocal body_bytes
            if body_bytes:
                b = body_bytes
                body_bytes = b""
                return {"type": "http.request", "body": b, "more_body": False}
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            messages.append(message)

        try:
            asyncio.run(self.app(scope, receive, send))
        except HTTPException as exc:  # pragma: no cover
            return SimpleResponse(exc.status_code, json.dumps({"detail": exc.detail}).encode())

        status_code = 500
        body = b""
        for message in messages:
            if message["type"] == "http.response.start":
                status_code = message["status"]
            elif message["type"] == "http.response.body":
                body += message.get("body", b"")
        return SimpleResponse(status_code, body)

    def get(self, path, headers=None):
        return self._request("GET", path, headers=headers)

    def post(self, path, json=None, headers=None):
        return self._request("POST", path, json_body=json, headers=headers)


client = SimpleClient(app)

def test_missing_users_file(tmp_path, monkeypatch):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_FILE", users_path)
    monkeypatch.setattr(middleware, "USERS_FILE", users_path)
    assert not users_path.exists()
    resp = client.get("/", headers={"Authorization": "Bearer whatever"})
    assert resp.status_code == 401
    assert users_path.exists()
    assert users_path.read_text() == "[]"
