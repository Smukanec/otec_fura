# Otec FURA (konsolidovaná)

Veřejná vrstva (wrapper) + původní FURA app (mount pod `/core`).

## Rychlý start (lokálně)
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt  # min: fastapi, uvicorn, httpx
cp .env.example .env             # vyplň MODEL_API_BASE, MODEL_API_KEY atd.
uvicorn app_ask:app --host 0.0.0.0 --port 8090
