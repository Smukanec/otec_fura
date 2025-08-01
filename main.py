from fastapi import FastAPI
from api.get_context import router as context_router
from api.auth import router as auth_router
from api.crawler_router import router as crawler_router

app = FastAPI(title="Otec Fura")

# Připojení všech routerů
app.include_router(context_router)
app.include_router(auth_router)
app.include_router(crawler_router)

@app.get("/")
async def root():
    return {"message": "Otec Fura API"}
