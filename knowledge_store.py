# -*- coding: utf-8 -*-
import os, io, json, time, pickle, logging, re, math
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import numpy as np

from sentence_transformers import SentenceTransformer
import faiss

from bs4 import BeautifulSoup
import requests

from pdfminer.high_level import extract_text as pdfminer_extract
from PyPDF2 import PdfReader

LOGGER = logging.getLogger("fura.knowledge")

def _now_ts() -> int:
    return int(time.time())

def _chunk_text(txt: str, max_chars=900, overlap=150) -> List[str]:
    txt = re.sub(r'\s+', ' ', (txt or '')).strip()
    if not txt:
        return []
    chunks = []
    i = 0
    n = len(txt)
    while i < n:
        j = min(n, i + max_chars)
        # prefer split at sentence end
        cut = txt[i:j]
        m = re.search(r'.*?[.!?](\s|$)', cut)
        if m and (i + m.end()) - i >= max_chars * 0.6:
            j = i + m.end()
        chunks.append(txt[i:j].strip())
        if j >= n:
            break
        i = max(0, j - overlap)
    return [c for c in chunks if c]

@dataclass
class DocMeta:
    id: str
    title: str
    source: str            # 'manual' | 'url' | 'file'
    tags: List[str] = field(default_factory=list)
    created_at: int = field(default_factory=_now_ts)

class KnowledgeStore:
    def __init__(self, root_dir: str):
        self.root = root_dir
        os.makedirs(self.root, exist_ok=True)
        self.store_path = os.path.join(self.root, "knowledge_store.jsonl")
        self.index_path = os.path.join(self.root, "knowledge_index.pkl")
        self.model_name = "sentence-transformers/all-MiniLM-L6-v2"
        self._model: Optional[SentenceTransformer] = None
        self._index: Optional[faiss.IndexFlatIP] = None
        self._vectors: Optional[np.ndarray] = None   # shape (N, D)
        self._entries: List[Dict] = []              # aligned with _vectors rows
        self._dim = 384
        self._load_store()
        self._load_index()

    # ---------- low-level ----------
    def _load_store(self):
        self._docs = []  # list[DocMeta]
        if os.path.exists(self.store_path):
            with open(self.store_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip(): continue
                    obj = json.loads(line)
                    self._docs.append(DocMeta(**obj))
        else:
            open(self.store_path, "a", encoding="utf-8").close()

    def _save_doc(self, meta: DocMeta):
        with open(self.store_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(meta.__dict__, ensure_ascii=False) + "\n")
        self._docs.append(meta)

    def _load_index(self):
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, "rb") as f:
                    data = pickle.load(f)
                self._vectors = data["vectors"].astype("float32")
                self._entries = data["entries"]
                self._dim = data.get("dim", 384)
                self._index = faiss.IndexFlatIP(self._dim)
                faiss.normalize_L2(self._vectors)
                self._index.add(self._vectors)
                LOGGER.info("Loaded knowledge index with %d vectors (%d dims) from %s",
                            self._vectors.shape[0], self._dim, self.index_path)
                return
            except Exception as e:
                LOGGER.warning("Failed to load index, will rebuild: %s", e)
        LOGGER.info("Knowledge index not found, will build on demand: %s", self.index_path)
        self._index = faiss.IndexFlatIP(self._dim)
        self._vectors = np.zeros((0, self._dim), dtype="float32")
        self._entries = []

    def _save_index(self):
        if self._vectors is None: return
        with open(self.index_path, "wb") as f:
            pickle.dump({
                "vectors": self._vectors.astype("float32"),
                "entries": self._entries,
                "dim": self._dim,
                "model": self.model_name,
            }, f)

    def _embedder(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def _embed(self, texts: List[str]) -> np.ndarray:
        if not texts: return np.zeros((0, self._dim), dtype="float32")
        vecs = self._embedder().encode(texts, normalize_embeddings=True)
        if isinstance(vecs, list):
            vecs = np.array(vecs)
        return vecs.astype("float32")

    def _add_vectors(self, vectors: np.ndarray, entries: List[Dict]):
        if vectors.size == 0: return
        if self._vectors is None or self._vectors.shape[0] == 0:
            self._vectors = vectors
            self._entries = entries
            self._index = faiss.IndexFlatIP(vectors.shape[1])
            self._index.add(vectors)
        else:
            self._vectors = np.vstack([self._vectors, vectors])
            self._entries.extend(entries)
            self._index.add(vectors)
        self._save_index()

    # ---------- public API ----------
    def add_manual(self, title: str, content: str, tags: Optional[List[str]] = None) -> Tuple[str,int]:
        doc_id = f"doc-{len(self._docs)+1}"
        meta = DocMeta(id=doc_id, title=title or "(bez názvu)", source="manual", tags=tags or [])
        self._save_doc(meta)
        chunks = _chunk_text(content or "")
        vecs = self._embed(chunks)
        entries = [ {"doc_id": doc_id, "title": meta.title, "source": meta.source,
                     "tags": meta.tags, "chunk": c} for c in chunks ]
        self._add_vectors(vecs, entries)
        return doc_id, len(chunks)

    def _fetch_url(self, url: str, timeout=15) -> Tuple[str, str]:
        headers = {"User-Agent":"Mozilla/5.0 (compatible; FuraBot/1.0; +https://jarvik-ai.tech)"}
        r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        ctype = (r.headers.get("content-type") or "").lower()
        return ctype, r.content

    def add_from_url(self, url: str) -> Tuple[str,int]:
        ctype, body = self._fetch_url(url)
        text = ""
        title = url
        if "pdf" in ctype or url.lower().endswith(".pdf"):
            try:
                # pdfminer
                text = pdfminer_extract(io.BytesIO(body))
            except Exception:
                # PyPDF2 fallback
                rd = PdfReader(io.BytesIO(body))
                text = "\n".join([p.extract_text() or "" for p in rd.pages])
        else:
            html = body.decode("utf-8", errors="ignore")
            soup = BeautifulSoup(html, "html.parser")
            title_tag = soup.find("title")
            if title_tag: title = title_tag.text.strip()
            # remove scripts/styles
            for bad in soup(["script","style","noscript"]): bad.decompose()
            text = (soup.get_text(" ") or "").strip()
        doc_id = f"doc-{len(self._docs)+1}"
        meta = DocMeta(id=doc_id, title=title or url, source="url", tags=["web"])
        self._save_doc(meta)
        chunks = _chunk_text(text)
        vecs = self._embed(chunks)
        entries = [ {"doc_id": doc_id, "title": meta.title, "source": meta.source,
                     "tags": meta.tags, "chunk": c, "url": url} for c in chunks ]
        self._add_vectors(vecs, entries)
        return doc_id, len(chunks)

    def add_from_file(self, path: str, title: Optional[str]=None, tags: Optional[List[str]]=None) -> Tuple[str,int]:
        path = os.path.abspath(path)
        base = os.path.basename(path)
        text = ""
        if base.lower().endswith(".pdf"):
            try:
                text = pdfminer_extract(path)
            except Exception:
                rd = PdfReader(path)
                text = "\n".join([p.extract_text() or "" for p in rd.pages])
        else:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        doc_id = f"doc-{len(self._docs)+1}"
        meta = DocMeta(id=doc_id, title=title or base, source="file", tags=tags or [])
        self._save_doc(meta)
        chunks = _chunk_text(text)
        vecs = self._embed(chunks)
        entries = [ {"doc_id": doc_id, "title": meta.title, "source": meta.source,
                     "tags": meta.tags, "chunk": c, "file": base} for c in chunks ]
        self._add_vectors(vecs, entries)
        return doc_id, len(chunks)

    def reindex_folder(self, folder: str) -> Dict[str,int]:
        folder = os.path.abspath(folder)
        os.makedirs(folder, exist_ok=True)
        added_docs = 0
        added_chunks = 0
        for name in os.listdir(folder):
            p = os.path.join(folder, name)
            if not os.path.isfile(p): continue
            if not any(name.lower().endswith(ext) for ext in (".md",".txt",".pdf")):
                continue
            doc_id, n = self.add_from_file(p)
            added_docs += 1
            added_chunks += n
        return {"docs": added_docs, "chunks": added_chunks}

    def search(self, query: str, top_k=5) -> List[Dict]:
        if not query.strip() or self._index is None or self._vectors.shape[0] == 0:
            return []
        q = self._embed([query])
        D, I = self._index.search(q, min(top_k, self._vectors.shape[0]))
        out = []
        for score, idx in zip(D[0].tolist(), I[0].tolist()):
            if idx < 0 or idx >= len(self._entries): continue
            e = self._entries[idx]
            out.append({
                "title": e.get("title") or "(bez názvu)",
                "source": e.get("source") or "",
                "tags": e.get("tags") or [],
                "score": float(score),
                "snippet": e.get("chunk","")[:450]
            })
        return out
