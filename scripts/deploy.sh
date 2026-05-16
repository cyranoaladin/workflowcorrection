#!/usr/bin/env bash
set -euo pipefail

cd /opt/math-correction

if [[ ! -f ".env" ]]; then
  echo "[deploy] Missing .env. Create it with: cp .env.example .env"
  exit 1
fi

echo "[deploy] Pull/build and start containers..."
docker compose up -d --build

echo "[deploy] Containers:"
docker compose ps

echo "[deploy] Backend logs (last 100 lines):"
docker compose logs --tail=100 backend || true

echo "[deploy] Health check:"
curl -fsS http://localhost:8000/health || (echo "[deploy] Health check failed" && exit 1)

echo "[deploy] OK"

