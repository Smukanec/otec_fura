# api/get_context.py
from fastapi import APIRouter, Request
from api.get_memory import load_memory_context, append_to_memory
from api.search_knowledge import search_knowledge
from api.embedder import embed_and_query

router = APIRouter()

@router.post("/get_context")
async def get_context(request: Request):
    body = await request.json()
    query = body.get("query", "") or ""
    user = body.get("user", "anonymous")

    # 1) načti „relevantní“ paměť (jen to, co obsahuje query)
    memory_ctx = load_memory_context(user, query)
    # 2) doplň ostatní kontexty
    knowledge_ctx = search_knowledge(query)
    embed_ctx = embed_and_query(query)

    # 3) ZAPIŠ DO PAMĚTI – ať to jde vidět v souboru
    append_to_memory(user, f"User '{user}' se ptal: {query}")

    return {
        "memory": memory_ctx,
        "knowledge": knowledge_ctx,
        "embedding": embed_ctx,
    }
