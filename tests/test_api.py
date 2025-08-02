import sys
import types
import json
import pytest

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
            return [0.1, 0.2]

    monkeypatch.setattr("api.crawler_router._get_model", lambda: DummyModel())
    monkeypatch.setattr(
        "api.web_crawler.crawl_url", lambda url, limit=500: ["dummy text"]
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
