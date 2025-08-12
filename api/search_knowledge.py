# api/search_knowledge.py
from typing import List

def search_knowledge(query: str) -> List[str]:
    # Sem si můžeš napojit BM25/SQLite/FAISS… Pro teď dummy:
    if not query:
        return []
    return []
