#!/bin/bash

# Zabít proces, pokud něco běží na portu 8090
PID=$(lsof -ti:8090)
if [ ! -z "$PID" ]; then
  echo "🔴 Port 8090 je obsazený (PID $PID) – ukončuji..."
  kill $PID
  sleep 1
fi

# Aktivace virtuálního prostředí (pokud existuje)
if [ -f "venv/bin/activate" ]; then
  source venv/bin/activate
fi

# Spuštění API serveru (FastAPI přes uvicorn)
echo "🚀 Spouštím Otec Fura na 0.0.0.0:8090"
uvicorn main:app --host 0.0.0.0 --port 8090
