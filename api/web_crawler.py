import requests
from bs4 import BeautifulSoup
from typing import List


def crawl_url(url: str, limit: int = 500) -> List[str]:
    """Jednoduchý crawler který vrátí text z dané URL."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    return [text[:limit]]
