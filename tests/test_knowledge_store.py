import numpy as np
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from knowledge_store import KnowledgeStore


def _dummy_embed(self, texts):
    return np.zeros((len(texts), self._dim), dtype="float32")


def _make_files(root: Path):
    (root / "a.txt").write_text("hello", encoding="utf-8")
    sub = root / "sub"
    sub.mkdir()
    (sub / "b.md").write_text("world", encoding="utf-8")
    deep = sub / "deep"
    deep.mkdir()
    (deep / "c.txt").write_text("deep", encoding="utf-8")


def test_reindex_nested_files(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _make_files(data_dir)
    store_dir = tmp_path / "store"
    ks = KnowledgeStore(str(store_dir))
    monkeypatch.setattr(KnowledgeStore, "_embed", _dummy_embed, raising=False)

    res1 = ks.reindex_folder(str(data_dir))
    assert res1 == {"docs": 3, "chunks": 3}
    res2 = ks.reindex_folder(str(data_dir))
    assert res2 == {"docs": 3, "chunks": 3}
    assert len(ks._docs) == 3
    assert ks._vectors.shape[0] == 3
