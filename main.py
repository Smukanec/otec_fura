# main.py
from fastapi import FastAPI
from middleware import APIKeyAuthMiddleware
from user_endpoint import router as user_router
from api.get_context import router as ctx_router

app = FastAPI(title="Otec Fura API")

# Povolené cesty bez auth (chceš-li vše zamknout, dej prázdnou množinu)
allow = {"/", "/openapi.json", "/docs", "/redoc", "/favicon.ico"}
app.add_middleware(APIKeyAuthMiddleware, allow_paths=allow)

@app.get("/")
def root():
    return {"message": "Otec Fura API OK"}

app.include_router(user_router)
app.include_router(ctx_router)
