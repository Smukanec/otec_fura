from fastapi import APIRouter, Request
from api.get_memory import load_memory_context, append_to_memory
from api.search_knowledge import search_knowledge
from api.embedder import embed_and_query

router = APIRouter()

@router.post("/get_context")
async def get_context(request: Request):
    body = await request.json()
    query = body.get("query", "") or ""
    user = body.get("user", "anonymous") or "anonymous"

    # 1) paměť
    memory_ctx = load_memory_context(user, query)

    # 2) znalosti (placeholder – ponechávám tvůj původní modul)
    knowledge_ctx = search_knowledge(query)

    # 3) embedding / RAG (placeholder – ponechávám tvůj původní modul)
    embed_ctx = embed_and_query(query)

    # 4) VOLITELNÝ zápis do paměti: pokud přijde "remember": true,
    #    uložíme i stručný záznam dotazu
    if body.get("remember"):
        append_to_memory(user, f"User '{user}' se ptal: {query}")

    return {
        "memory": memory_ctx,
        "knowledge": knowledge_ctx,
        "embedding": embed_ctx,
    }
