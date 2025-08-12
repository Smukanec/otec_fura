#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# aktivuj venv, ale uvicorn spouštěj přes python -m (spolehlivější v systemd)
source venv/bin/activate
exec python3 -m uvicorn main:app --host 0.0.0.0 --port 8090
