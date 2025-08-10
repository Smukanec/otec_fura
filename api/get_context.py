# api/get_context.py
from fastapi import APIRouter, Request
from api.get_memory import load_memory_context, append_to_memory
from api.search_knowledge import search_knowledge
from api.embedder import embed_and_query

router = APIRouter()

@router.post("/get_context")
async def get_context(request: Request):
    body = await request.json()
    query = body.get("query", "")
    user = body.get("user", "anonymous")

    memory_ctx = load_memory_context(user, query)
    knowledge_ctx = search_knowledge(query)
    embed_ctx = embed_and_query(query)

    # pokus o zápis do paměti (nebrzdí odpověď)
    try:
        if query:
            append_to_memory(user, query, "Zaznamenán dotaz přes /get_context.")
    except Exception as e:
        # jednoduchý log do konzole (u systemd uvidíš v journalctl)
        print(f"[get_context] append_to_memory failed: {e}")

    return {
        "memory": memory_ctx,
        "knowledge": knowledge_ctx,
        "embedding": embed_ctx,
    }
