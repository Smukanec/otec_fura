# api/get_context.py
from fastapi import APIRouter
from pydantic import BaseModel
from api.get_memory import load_memory_context, append_to_memory
from api.search_knowledge import search_knowledge
from api.embedder import embed_and_query

router = APIRouter()

class GetContextRequest(BaseModel):
    query: str = ""
    user: str = "anonymous"
    remember: bool = False


@router.post("/get_context")
async def get_context(body: GetContextRequest):
    query = body.query
    user = body.user
    remember = body.remember

    memory_ctx = load_memory_context(user, query)
    knowledge_ctx = search_knowledge(query)
    embed_ctx = embed_and_query(query)

    if remember and query.strip():
        append_to_memory(user, f"{query} - Zaznamenán dotaz přes /get_context.")

    return {
        "memory": memory_ctx,
        "knowledge": knowledge_ctx,
        "embedding": embed_ctx,
    }
