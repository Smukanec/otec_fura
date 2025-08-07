from fastapi import FastAPI
from api.get_context import router as context_router
from api.auth import router as auth_router
from api.crawler_router import router as crawler_router
from api.user_endpoint import router as user_router  # ⬅️ Přidat
from middleware import APIKeyMiddleware

app = FastAPI(title="Otec Fura")

# Middleware pro ověření API klíče
app.add_middleware(APIKeyMiddleware)

# Připojení všech routerů
app.include_router(context_router)
app.include_router(auth_router)
app.include_router(crawler_router)
app.include_router(user_router)  # ⬅️ Přidat

@app.get("/")
async def root():
    return {"message": "Otec Fura API"}
