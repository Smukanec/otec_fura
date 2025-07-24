from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"


def _search_in_file(file_path: Path, query_lower: str) -> list[str]:
    results = []
    with file_path.open("r", encoding="utf-8") as f:
        for line in f:
            if query_lower in line.lower():
                results.append(line.strip())
    return results


def search_knowledge(query: str) -> list[str]:
    """Jednoduché fulltextové vyhledávání v souborech."""
    query_lower = query.lower()
    matches = []
    for path in KNOWLEDGE_DIR.rglob("*.txt"):
        matches.extend(_search_in_file(path, query_lower))
    return matches
