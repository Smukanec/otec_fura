# Adresářová struktura pro Otce Furu (server 2)

otec_fura/
├── api/
│   ├── __init__.py
│   ├── get_context.py      # hlavní API endpoint pro dotaz
│   ├── get_memory.py       # čte paměť podle userID
│   ├── search_knowledge.py # hledá ve knowledge složce
│   ├── embedder.py         # sentence-transformers model
│   └── web_crawler.py      # volitelný web search modul
├── memory/
│   ├── public.jsonl
│   └── jiri/
│       ├── private.jsonl
│       └── meta.json
├── knowledge/
│   ├── ai/
│   ├── auto/
│   ├── zdraví/
│   └── ...
├── embeddings/
│   └── faiss_index.bin     # embedding index
├── data/
│   └── docs_cleaned/       # normalizované znalosti
├── main.py                 # FastAPI runner (uvicorn)
├── pyproject.toml       # project metadata and dependencies
└── config.py


# API endpoint: get_context.py

from fastapi import APIRouter, Request
from api.get_memory import load_memory_context
from api.search_knowledge import search_knowledge
from api.embedder import embed_and_query

router = APIRouter()

@router.post("/get_context")
async def get_context(request: Request):
    body = await request.json()
    query = body.get("query")
    user = body.get("user", "anonymous")

    memory_ctx = load_memory_context(user, query)
    knowledge_ctx = search_knowledge(query)
    embed_ctx = embed_and_query(query)

    return {
        "memory": memory_ctx,
        "knowledge": knowledge_ctx,
        "embedding": embed_ctx
    }


# FastAPI spouštěč (main.py)

from fastapi import FastAPI
from api.get_context import router as context_router

app = FastAPI()
app.include_router(context_router)

# Spustit pomocí:
# uvicorn main:app --host 0.0.0.0 --port 8090


# Závislosti (pyproject.toml)
fastapi
uvicorn
sentence-transformers
faiss-cpu
pandas
python-multipart
requests
beautifulsoup4
