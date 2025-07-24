from fastapi import APIRouter, Request
from pathlib import Path
import json

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover - optional dependency
    SentenceTransformer = None

from api.web_crawler import crawl_url

WEB_INDEX_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "web_index.json"

_router_model = None

def _get_model():
    global _router_model
    if _router_model is None and SentenceTransformer is not None:
        _router_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _router_model

router = APIRouter()


@router.post("/crawl")
async def crawl_url_api(request: Request):
    body = await request.json()
    url = body.get("url")
    if not url:
        return {"error": "Missing URL"}

    texts = crawl_url(url)
    if not texts:
        return {"error": "Failed to crawl"}
    text = texts[0]

    model = _get_model()
    if model is None:
        return {"error": "Embedding model not available"}

    embedding = model.encode(text)
    index = {"url": url, "text": text, "embedding": embedding.tolist()}
    with WEB_INDEX_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(index) + "\n")

    return {"status": "OK", "chars": len(text)}
