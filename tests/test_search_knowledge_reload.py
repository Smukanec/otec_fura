import sys
from pathlib import Path

import pytest

# Ensure module import path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from api import search_knowledge


def test_new_files_become_searchable(tmp_path, monkeypatch):
    # Point the knowledge loader to a temporary directory
    monkeypatch.setattr(search_knowledge, "KNOWLEDGE_DIR", tmp_path)
    search_knowledge.reload_knowledge()

    # Initial file and query to populate caches
    (tmp_path / "first.txt").write_text("alpha beta", encoding="utf-8")
    assert any("alpha" in r for r in search_knowledge.search_knowledge("alpha"))

    # Add new file after initial load
    (tmp_path / "second.txt").write_text("fresh fact", encoding="utf-8")

    # The new file should be discovered without restarting
    results = search_knowledge.search_knowledge("fresh")
    assert any("fresh" in r for r in results)
