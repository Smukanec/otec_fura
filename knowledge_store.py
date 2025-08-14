import os
import io
import json
import pickle
import threading
import logging
from typing import List, Dict, Optional, Tuple

import numpy as np

try:
    from sentence_transformers import SentenceTransformer
except Exception as e:
    SentenceTransformer = None  # lazy import in _get_model

from bs4 import BeautifulSoup
from PyPDF2 import PdfReader
try:
    from pdfminer.high_level import extract_text as pdfminer_extract_text
except Exception:
    pdfminer_extract_text = None

LOGGER = logging.getLogger("fura.knowledge")


def _read_text_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        LOGGER.warning("Failed to read text file %s: %s", path, e)
        return ""


def _extract_text_from_pdf(path: str) -> str:
    # First try PyPDF2
    try:
        reader = PdfReader(path)
        parts = []
        for page in reader.pages:
            txt = page.extract_text() or ""
            parts.append(txt)
        text = "\n".join(parts).strip()
        if text:
            return text
    except Exception as e:
        LOGGER.warning("PyPDF2 failed on %s: %s", path, e)

    # Fallback to pdfminer.six
    if pdfminer_extract_text:
        try:
            text = pdfminer_extract_text(path) or ""
            return text.strip()
        except Exception as e:
            LOGGER.warning("pdfminer failed on %s: %s", path, e)

    return ""


def _clean_text(s: str) -> str:
    s = s.replace("\r", "\n")
    s = "\n".join(line.strip() for line in s.split("\n"))
    # squeeze multiple newlines
    s = "\n".join([ln for ln in s.split("\n") if ln.strip() != ""])
    return s.strip()


def _chunk_text(s: str, max_chars: int = 1500, overlap: int = 150) -> List[str]:
    """Very simple char-based chunking to make search useful on long docs."""
    s = _clean_text(s)
    if len(s) <= max_chars:
        return [s] if s else []
    chunks = []
    start = 0
    while start < len(s):
        end = min(len(s), start + max_chars)
        chunks.append(s[start:end])
        if end == len(s):
            break
        start = max(0, end - overlap)
    return chunks


class KnowledgeStore:
    """
    Minimal file-based knowledge store with in-memory embeddings,
    saved to pickle for fast reload.
    """
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.knowledge_dir = os.path.join(base_dir, "knowledge")
        os.makedirs(self.knowledge_dir, exist_ok=True)

        self.index_path = os.path.join(base_dir, "knowledge_index.pkl")

        self._model = None
        self._lock = threading.RLock()

        # data
        self._embeddings: Optional[np.ndarray] = None  # shape (N, D)
        self._items: List[Dict] = []  # each item = {"id","title","source","tags","chunk","doc_id"}
        self._doc_counter = 0

    # ---------- embedding model ----------
    def _get_model(self):
        if self._model is None:
            if SentenceTransformer is None:
                from sentence_transformers import SentenceTransformer as ST
            else:
                ST = SentenceTransformer
            # small, fast model
            self._model = ST("sentence-transformers/all-MiniLM-L6-v2")
        return self._model

    def _embed(self, texts: List[str]) -> np.ndarray:
        model = self._get_model()
        vecs = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return vecs.astype(np.float32)

    # ---------- persistence ----------
    def save(self):
        with self._lock:
            with open(self.index_path, "wb") as f:
                payload = {
                    "items": self._items,
                    "embeddings": self._embeddings,
                    "doc_counter": self._doc_counter,
                }
                pickle.dump(payload, f)
        LOGGER.info("Knowledge index saved: %s (items=%d)", self.index_path, len(self._items))

    def load(self):
        if not os.path.exists(self.index_path):
            LOGGER.info("Knowledge index not found, will build on demand: %s", self.index_path)
            return
        try:
            with open(self.index_path, "rb") as f:
                payload = pickle.load(f)
            self._items = payload.get("items", [])
            self._embeddings = payload.get("embeddings", None)
            self._doc_counter = payload.get("doc_counter", 0)
            LOGGER.info("Knowledge index loaded: %s (items=%d)", self.index_path, len(self._items))
        except Exception as e:
            LOGGER.error("Failed to load index %s: %s", self.index_path, e)

    # ---------- add/search ----------
    def add_document(self, title: str, content: str, source: Optional[str] = None, tags: Optional[List[str]] = None) -> Dict:
        content = _clean_text(content or "")
        if not content:
            raise ValueError("Empty content")

        with self._lock:
            self._doc_counter += 1
            doc_id = f"doc-{self._doc_counter}"

            chunks = _chunk_text(content)
            if not chunks:
                raise ValueError("No textual content after cleaning")

            embs = self._embed(chunks)

            # append
            if self._embeddings is None:
                self._embeddings = embs
            else:
                self._embeddings = np.vstack([self._embeddings, embs])

            start_idx = len(self._items)
            for i, ch in enumerate(chunks):
                self._items.append({
                    "id": f"{doc_id}-chunk-{i+1}",
                    "doc_id": doc_id,
                    "title": title,
                    "source": source or "manual",
                    "tags": tags or [],
                    "chunk": ch,
                })

            self.save()
            return {"ok": True, "id": doc_id, "title": title, "chunks": len(chunks)}

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        with self._lock:
            if self._embeddings is None or len(self._items) == 0:
                return []
            q = self._embed([query])[0]  # (D,)
            # cosine sim since embeddings are normalized = dot product
            sims = np.dot(self._embeddings, q)  # (N,)
            idxs = np.argsort(-sims)[:max(1, top_k)]
            out = []
            for i in idxs:
                item = self._items[int(i)]
                out.append({
                    "title": item["title"],
                    "source": item["source"],
                    "tags": item["tags"],
                    "score": float(sims[int(i)]),
                    "snippet": item["chunk"][:500],
                })
            return out

    # ---------- reindex ----------
    def reindex_folder(self, folder: Optional[str] = None) -> Dict:
        folder = folder or self.knowledge_dir
        files = []
        for root, _, names in os.walk(folder):
            for nm in names:
                p = os.path.join(root, nm)
                if nm.lower().endswith((".txt", ".md", ".pdf")):
                    files.append(p)

        if not files:
            return {"ok": True, "indexed": 0, "detail": "No files"}

        # reset
        with self._lock:
            self._items = []
            self._embeddings = None
            self._doc_counter = 0

        count_docs = 0
        for path in files:
            title = os.path.basename(path)
            text = ""
            if path.lower().endswith(".pdf"):
                text = _extract_text_from_pdf(path)
            else:
                text = _read_text_file(path)

            text = _clean_text(text)
            if not text:
                LOGGER.warning("Empty text for %s", path)
                continue

            try:
                self.add_document(title=title, content=text, source=f"file:{path}", tags=["file"])
                count_docs += 1
            except Exception as e:
                LOGGER.warning("Failed to add %s: %s", path, e)

        return {"ok": True, "indexed": count_docs}
