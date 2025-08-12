# main.py
from fastapi import FastAPI, Request
from middleware import APIKeyMiddleware
from api.get_context import router as context_router
from user_endpoint import router as user_router

app = FastAPI(title="Otec Fura API")

# middleware s kontrolou API klíče
app.add_middleware(APIKeyMiddleware)

@app.get("/")
async def root(request: Request):
    # i kořen vyžaduje klíč (pokud ho pošleš, dostaneš 200 OK)
    return {"message": "Otec Fura API OK"}

# endpoints
app.include_router(user_router)
app.include_router(context_router)
