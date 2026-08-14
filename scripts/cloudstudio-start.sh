#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_PID=""
BACKEND_PID=""

cleanup() {
  if [[ -n "$BACKEND_PID" ]]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "$FRONTEND_PID" ]]; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

cd "$PROJECT_ROOT/frontend"
if [[ ! -x node_modules/.bin/next ]]; then
  echo "Frontend dependencies are missing or incomplete; running npm ci..."
  npm ci
fi

if [[ ! -x node_modules/.bin/next ]]; then
  echo "Next.js installation failed: node_modules/.bin/next was not created." >&2
  exit 1
fi

npm run build
npm run start -- --hostname 0.0.0.0 --port 3000 &
FRONTEND_PID=$!

for _ in $(seq 1 60); do
  if curl --fail --silent --output /dev/null http://127.0.0.1:3000/login; then
    break
  fi
  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    wait "$FRONTEND_PID"
  fi
  sleep 1
done

cd "$PROJECT_ROOT/backend"
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

wait -n "$FRONTEND_PID" "$BACKEND_PID"
