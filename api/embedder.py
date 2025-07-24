from pathlib import Path
from typing import List
import json

try:
    from sentence_transformers import SentenceTransformer, util
except ImportError:  # pragma: no cover - optional dependency
    SentenceTransformer = None
    util = None

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"
MEMORY_DIR = Path(__file__).resolve().parent.parent / "memory"

_model = None

def _get_model():
    global _model
    if _model is None and SentenceTransformer is not None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _load_corpus() -> List[str]:
    texts = []
    for path in KNOWLEDGE_DIR.rglob("*.txt"):
        texts.append(path.read_text(encoding="utf-8"))
    for path in MEMORY_DIR.rglob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    texts.append(json.loads(line).get("text", ""))
                except Exception:
                    pass
    return texts


def embed_and_query(query: str, top_k: int = 3) -> List[str]:
    """Vrátí nejpodobnější texty z korpusu pomocí embeddingu."""
    if SentenceTransformer is None:
        return []
    model = _get_model()
    corpus = _load_corpus()
    if not corpus:
        return []
    corpus_embeddings = model.encode(corpus, convert_to_tensor=True)
    query_emb = model.encode(query, convert_to_tensor=True)
    hits = util.semantic_search(query_emb, corpus_embeddings, top_k=top_k)[0]
    return [corpus[hit["corpus_id"]] for hit in hits]
