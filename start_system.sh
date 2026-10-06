#!/usr/bin/env bash

echo "=========================================================="
echo "🚀 AUTONOMOUS CAREER AGENT ENGINE - STARTUP SEQUENCE"
echo "=========================================================="

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# 1. Check Python Virtualenv
if [ ! -d "backend/.venv" ]; then
    echo "[!] Virtualenv not found. Creating..."
    python3 -m venv backend/.venv
    ./backend/.venv/bin/pip install -r backend/requirements.txt
fi

# Load .env with dotenv's parser rather than sourcing it as shell code.
if [ -f "$DIR/.env" ] && [ "${CAREER_ENV_LOADED:-}" != "1" ]; then
    exec "$DIR/backend/.venv/bin/dotenv" -f "$DIR/.env" run -- /usr/bin/env CAREER_ENV_LOADED=1 "$0" "$@"
fi

# Local only by default: single-user mode has no login, so the API must not be reachable from the network.
BACKEND_HOST="${API_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-${API_PORT:-8000}}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
UVICORN_WORKERS="${UVICORN_WORKERS:-1}"

echo "[*] Launching FastAPI Backend on http://${BACKEND_HOST}:${BACKEND_PORT} ..."
PYTHONPATH=. API_PORT="$BACKEND_PORT" ./backend/.venv/bin/python3 -m uvicorn backend.app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" --workers "$UVICORN_WORKERS" &
BACKEND_PID=$!

echo "[*] Launching Next.js Web Dashboard on http://${FRONTEND_HOST}:${FRONTEND_PORT} ..."
cd frontend && NEXT_PUBLIC_API_URL="${PUBLIC_API_URL:-http://localhost:${BACKEND_PORT}/api}" npm run dev -- -H "$FRONTEND_HOST" -p "$FRONTEND_PORT" &
FRONTEND_PID=$!

echo "=========================================================="
echo "✓ Backend API Docs:       http://localhost:${BACKEND_PORT}/docs"
echo "✓ Web Management UI:      http://${FRONTEND_HOST}:${FRONTEND_PORT}"
echo "✓ LinkedIn Handshake:     Eklenti veya /safety sayfasından aktif"
echo "✓ Celery + Redis Kuyruğu: Dual-Mode (Docker Compose veya Asenkron)"
echo "✓ OAuth2 Gelen Kutu:      Gmail & Outlook API /inbox sayfasında"
echo "=========================================================="
echo "Press CTRL+C to stop all services."

trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT TERM
wait
