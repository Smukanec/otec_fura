"""Utilities for embedding queries and searching the knowledge store."""

from __future__ import annotations

from pathlib import Path
from typing import List

from knowledge_store import KnowledgeStore

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

_model = None
_store: KnowledgeStore | None = None


def _get_model():
    """Return a cached instance of :class:`SentenceTransformer`.

    Raises
    ------
    RuntimeError
        If the ``sentence-transformers`` package is not installed.
    """

    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - handled in tests
            raise RuntimeError(
                "sentence-transformers package is required for embeddings"
            ) from exc
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def _get_store() -> KnowledgeStore:
    """Return a cached :class:`KnowledgeStore` instance."""

    global _store
    if _store is None:
        root = Path(__file__).resolve().parents[1]
        _store = KnowledgeStore(str(root))
    return _store


def embed_and_query(query: str, top_k: int = 3) -> List[str]:
    """Embed ``query`` and retrieve matching snippets from the knowledge store.

    Parameters
    ----------
    query:
        Textual user query.
    top_k:
        Maximum number of snippets to return.
    """

    query = (query or "").strip()
    if not query:
        return []

    # Ensure the embedding model is available.  We do not use the actual
    # embedding further because :class:`KnowledgeStore` performs its own
    # embedding internally, but calling ``encode`` validates that the model can
    # be loaded and produces a vector.
    model = _get_model()
    model.encode([query])

    store = _get_store()
    hits = store.search(query, top_k=top_k)
    return [h["snippet"] for h in hits]
