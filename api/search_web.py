"""Simple vector similarity search over crawled web pages.

The crawler API stores fetched pages in ``knowledge/web_index.json`` as
line-delimited JSON objects with the following structure::

    {"url": "http://example.com", "text": "…", "embedding": [0.1, 0.2, …]}

This module loads these entries on demand and allows querying them using
cosine similarity.  Embeddings are expected to be compatible with the
``all-MiniLM-L6-v2`` model used elsewhere in the project.  The dependency on
``sentence-transformers`` is optional; when the package is not available the
search simply returns an empty list.
"""

from __future__ import annotations

from pathlib import Path
import json
from typing import List

import numpy as np

try:  # pragma: no cover - optional dependency
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover - handled gracefully
    SentenceTransformer = None

# Path to the line-delimited JSON file produced by ``/crawl``
WEB_INDEX_PATH = Path(__file__).resolve().parents[1] / "knowledge" / "web_index.json"

_model: SentenceTransformer | None = None
_entries: List[dict] = []
_vectors: np.ndarray | None = None
_mtime: float | None = None


def _get_model() -> SentenceTransformer | None:
    """Return a cached embedding model if available."""

    global _model
    if _model is None and SentenceTransformer is not None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def reload_web_index() -> None:
    """Clear the cached index forcing a reload on next search."""

    global _entries, _vectors, _mtime
    _entries = []
    _vectors = None
    _mtime = None


def _load_index() -> None:
    """Load ``WEB_INDEX_PATH`` if it changed since the last read."""

    global _entries, _vectors, _mtime

    path = WEB_INDEX_PATH
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = None

    if _mtime is not None and mtime == _mtime:
        return  # Index unchanged

    _entries = []
    vectors: List[List[float]] = []

    if mtime is not None:
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    _entries.append(obj)
                    vectors.append(obj.get("embedding", []))
        except OSError:
            pass

    if vectors:
        arr = np.array(vectors, dtype=float)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        _vectors = arr / norms
    else:
        _vectors = np.zeros((0, 0), dtype=float)

    _mtime = mtime


def search_web(query: str, top_k: int = 3) -> List[str]:
    """Return snippets from crawled web pages relevant to ``query``.

    Parameters
    ----------
    query:
        User query to embed and compare with stored page embeddings.
    top_k:
        Maximum number of results to return.
    """

    query = (query or "").strip()
    if not query:
        return []

    _load_index()
    if not _entries or _vectors is None or _vectors.size == 0:
        return []

    model = _get_model()
    if model is None:
        return []

    q_vec = np.asarray(model.encode([query])[0], dtype=float)
    q_norm = np.linalg.norm(q_vec)
    if q_norm == 0:
        return []
    q_vec /= q_norm

    sims = _vectors.dot(q_vec)
    idx = np.argsort(-sims)[:top_k]

    results: List[str] = []
    for i in idx:
        entry = _entries[i]
        url = entry.get("url", "")
        text = entry.get("text", "")
        snippet = text[:200]
        results.append(f"{url}: {snippet}")
    return results


__all__ = ["search_web", "reload_web_index", "WEB_INDEX_PATH"]

