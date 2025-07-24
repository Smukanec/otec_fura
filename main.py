from fastapi import FastAPI
from api.get_context import router as context_router
from api.crawler_router import router as crawler_router

app = FastAPI(title="Otec Fura")
app.include_router(context_router)
app.include_router(crawler_router)


@app.get("/")
async def root():
    return {"message": "Otec Fura API"}

# Uvicorn spouštění:
# uvicorn main:app --host 0.0.0.0 --port 8090
