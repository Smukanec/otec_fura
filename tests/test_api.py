import sys
import types
import json
import pytest
import asyncio
from pathlib import Path
from fastapi import HTTPException, Request

sys.path.append(str(Path(__file__).resolve().parents[1]))

# Stub bcrypt to avoid external dependency in tests
bcrypt_stub = types.SimpleNamespace(
    hashpw=lambda password, salt: password,
    gensalt=lambda: b"salt",
    checkpw=lambda password, hashed: password == hashed,
)
sys.modules["bcrypt"] = bcrypt_stub

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
        except HTTPException as exc:  # pragma: no cover - handled similarly to TestClient
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


@pytest.fixture(autouse=True)
def users_file(tmp_path, monkeypatch):
    users_path = tmp_path / "users.json"
    users_path.write_text("[]")
    monkeypatch.setattr(auth, "USERS_FILE", users_path)
    monkeypatch.setattr(middleware, "USERS_FILE", users_path)
    return users_path


@pytest.fixture
def auth_header(users_file):
    resp = client.post(
        "/auth/register",
        json={"username": "tester", "password": "secret", "email": "tester@example.com"},
    )
    assert resp.status_code == 200
    users = json.loads(users_file.read_text())
    users[0]["approved"] = True
    users_file.write_text(json.dumps(users))
    resp = client.post(
        "/auth/token", json={"username": "tester", "password": "secret"}
    )
    assert resp.status_code == 200
    api_key = resp.json()["api_key"]
    return {"Authorization": f"Bearer {api_key}"}


def test_root(auth_header):
    resp = client.get("/", headers=auth_header)
    assert resp.status_code == 200
    assert resp.json() == {"message": "Otec Fura API"}


def test_current_user_in_state(auth_header):
    @app.get("/me")
    def me(request: Request):
        return request.state.current_user

    resp = client.get("/me", headers=auth_header)
    assert resp.status_code == 200
    assert resp.json()["username"] == "tester"


def test_get_context(monkeypatch, auth_header):
    def dummy_embed(query: str, top_k: int = 3):
        return [f"embedded:{query}"]

    monkeypatch.setattr("api.get_context.embed_and_query", dummy_embed)

    resp = client.post(
        "/get_context",
        json={"query": "transformers", "user": "jiri"},
        headers=auth_header,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == {"memory", "knowledge", "embedding"}
    assert isinstance(data["memory"], list)
    assert isinstance(data["knowledge"], list)
    assert data["embedding"] == ["embedded:transformers"]


def test_crawl(monkeypatch, tmp_path, auth_header):
    class DummyModel:
        def encode(self, text):
            return types.SimpleNamespace(tolist=lambda: [0.1, 0.2])

    monkeypatch.setattr("api.crawler_router._get_model", lambda: DummyModel())
    monkeypatch.setattr(
        "api.crawler_router.crawl_url", lambda url: ["dummy text"]
    )
    index_file = tmp_path / "index.json"
    monkeypatch.setattr("api.crawler_router.WEB_INDEX_PATH", index_file)

    resp = client.post(
        "/crawl", json={"url": "http://example.com"}, headers=auth_header
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "OK", "chars": len("dummy text")}
    assert index_file.exists()
    data = index_file.read_text(encoding="utf-8").strip()
    assert data
    item = json.loads(data)
    assert item["url"] == "http://example.com"
    assert item["text"] == "dummy text"
    assert item["embedding"] == [0.1, 0.2]


def test_get_context_unauthorized(monkeypatch):
    def dummy_embed(query: str, top_k: int = 3):
        return [f"embedded:{query}"]

    monkeypatch.setattr("api.get_context.embed_and_query", dummy_embed)

    resp = client.post(
        "/get_context", json={"query": "transformers", "user": "jiri"}
    )
    assert resp.status_code == 401


def test_register_does_not_return_api_key(users_file):
    resp = client.post(
        "/auth/register",
        json={"username": "novak", "password": "tajne", "email": "novak@example.com"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "api_key" not in data

    resp = client.post(
        "/auth/token", json={"username": "novak", "password": "tajne"}
    )
    assert resp.status_code == 403


def test_auth_me(auth_header):
    resp = client.get("/auth/me", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "tester"
    assert data["email"] == "tester@example.com"
    assert data["approved"] is True
