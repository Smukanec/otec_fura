from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.get_context import router as context_router
from api.auth import router as auth_router
from api.crawler_router import router as crawler_router
from api.user_endpoint import router as user_router  # ← /user endpoint
from middleware import APIKeyMiddleware

app = FastAPI(title="Otec Fura")

# CORS (případně přidej svoji doménu)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # nebo ["https://jarvik-ai.tech"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ověření Bearer tokenu
app.add_middleware(APIKeyMiddleware)

# Routery
app.include_router(user_router)      # /user
app.include_router(context_router)   # /get_context
app.include_router(auth_router)
app.include_router(crawler_router)

@app.get("/")
async def root():
    return {"message": "Otec Fura API OK"}
