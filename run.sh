#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# Dostupný lsof na serveru? Pokud ne, nevadí – jen přeskočíme kontrolu
if command -v lsof >/dev/null 2>&1; then
  if lsof -Pi :8090 -sTCP:LISTEN -t >/dev/null ; then
    PID=$(lsof -Pi :8090 -sTCP:LISTEN -t | head -n1)
    echo "🔴 Port 8090 je obsazený (PID $PID) – ukončuji..."
    kill -TERM "$PID" || true
    sleep 2
  fi
fi

echo "🚀 Spouštím Otec Fura na 0.0.0.0:8090"

# Aktivace venv
if [ -f venv/bin/activate ]; then
  source venv/bin/activate
fi

# Start
exec venv/bin/uvicorn main:app --host 0.0.0.0 --port 8090
