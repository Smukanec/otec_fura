from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_root():
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json() == {"message": "Otec Fura API"}


def test_get_context(monkeypatch):
    def dummy_embed(query: str, top_k: int = 3):
        return [f"embedded:{query}"]

    monkeypatch.setattr("api.get_context.embed_and_query", dummy_embed)

    resp = client.post(
        "/get_context",
        json={"query": "transformers", "user": "jiri"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == {"memory", "knowledge", "embedding"}
    assert isinstance(data["memory"], list)
    assert isinstance(data["knowledge"], list)
    assert data["embedding"] == ["embedded:transformers"]
