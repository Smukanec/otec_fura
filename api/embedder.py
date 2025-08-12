# api/embedder.py
from typing import List

def embed_and_query(query: str) -> List[str]:
    # Dummy výstup, ať je vidět, že endpoint žije
    base = [
        "Vítejte v paměti veřejných informací.",
        "Toto je soukromá paměť uživatele Jiri.",
        "Transformers jsou architektura deep learningu založená na mechanismu attention.\n",
    ]
    return base
