from fastapi import APIRouter, Request
from api.get_memory import load_memory_context
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

    return {
        "memory": memory_ctx,
        "knowledge": knowledge_ctx,
        "embedding": embed_ctx,
    }
