"""Utilities for querying the local knowledge base.

The repository ships with a tiny set of text files inside the ``knowledge``
directory.  The original implementation of :func:`search_knowledge` returned an
empty list which meant that ``/get_context`` never provided any meaningful
results.  For tests and simple experiments we implement a very small BM25 style
retriever directly in Python so we do not rely on heavy external packages.

The retriever loads all ``.txt`` files from the ``knowledge`` folder on first
use, tokenises them and computes inverse document frequencies.  Queries are then
scored against the documents using the BM25 formula and the best matching
snippets are returned.  Each snippet is a line of text from the document that
contains a query term (the whole document is used as a fallback).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path
from typing import List

# Path to the knowledge directory relative to this file
KNOWLEDGE_DIR = Path(__file__).resolve().parents[1] / "knowledge"

_documents: List[str] = []
_doc_tokens: List[List[str]] = []
_idf: dict[str, float] = {}
_avgdl: float = 0.0
_loaded = False


def _load_knowledge() -> None:
    """Load documents and pre-compute statistics for BM25."""

    global _loaded, _documents, _doc_tokens, _idf, _avgdl
    if _loaded:
        return

    if not KNOWLEDGE_DIR.exists():
        _loaded = True
        return

    # Read all text files inside the knowledge directory
    for path in KNOWLEDGE_DIR.glob("**/*.txt"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        _documents.append(text)
        _doc_tokens.append(re.findall(r"\w+", text.lower()))

    if not _documents:
        _loaded = True
        return

    lengths = [len(toks) for toks in _doc_tokens]
    _avgdl = sum(lengths) / len(lengths)

    # document frequencies
    df = Counter()
    for tokens in _doc_tokens:
        df.update(set(tokens))
    N = len(_documents)
    _idf = {term: math.log(1 + (N - freq + 0.5) / (freq + 0.5)) for term, freq in df.items()}

    _loaded = True


def search_knowledge(query: str, top_k: int = 3) -> List[str]:
    """Return snippets from the knowledge base matching ``query``.

    Parameters
    ----------
    query:
        The user query.
    top_k:
        Maximum number of snippets to return.
    """

    _load_knowledge()
    if not query or not _documents:
        return []

    q_tokens = re.findall(r"\w+", query.lower())
    if not q_tokens:
        return []

    k1, b = 1.5, 0.75
    scores = []
    for tokens, doc in zip(_doc_tokens, _documents):
        dl = len(tokens) or 1
        tf = Counter(tokens)
        score = 0.0
        for q in q_tokens:
            if q not in tf:
                continue
            idf = _idf.get(q, 0.0)
            freq = tf[q]
            score += idf * (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * dl / _avgdl))
        scores.append(score)

    # Sort documents by score and build snippets
    results: List[str] = []
    for idx in sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]:
        if scores[idx] <= 0:
            continue
        doc = _documents[idx]
        # Find a line containing any of the query terms
        snippet = doc
        for line in doc.splitlines():
            if any(q in line.lower() for q in q_tokens):
                snippet = line.strip()
                break
        results.append(snippet)

    return results

