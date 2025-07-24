from fastapi.testclient import TestClient
from main import app
import json

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


def test_crawl(monkeypatch, tmp_path):
    class DummyModel:
        def encode(self, text):
            return [0.1, 0.2]

    monkeypatch.setattr("api.crawler_router._get_model", lambda: DummyModel())
    monkeypatch.setattr("api.web_crawler.crawl_url", lambda url, limit=500: ["dummy text"])
    index_file = tmp_path / "index.json"
    monkeypatch.setattr("api.crawler_router.WEB_INDEX_PATH", index_file)

    resp = client.post("/crawl", json={"url": "http://example.com"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "OK", "chars": len("dummy text")}
    assert index_file.exists()
    data = index_file.read_text(encoding="utf-8").strip()
    assert data
    item = json.loads(data)
    assert item["url"] == "http://example.com"
    assert item["text"] == "dummy text"
    assert item["embedding"] == [0.1, 0.2]
