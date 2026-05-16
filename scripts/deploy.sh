#!/usr/bin/env bash
set -euo pipefail

cd /opt/math-correction

ENV_FILE="${APP_ENV_FILE:-./.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "[deploy] Missing env file '$ENV_FILE'."
  echo "[deploy] Create it with: cp .env.production.example .env  (then fill in all values)"
  exit 1
fi

echo "[deploy] Pull/build and start containers (production compose)..."
docker compose -f docker-compose.prod.yml --env-file "$ENV_FILE" up -d --build

echo "[deploy] Containers:"
docker compose -f docker-compose.prod.yml --env-file "$ENV_FILE" ps

echo "[deploy] Backend logs (last 100 lines):"
docker compose -f docker-compose.prod.yml --env-file "$ENV_FILE" logs --tail=100 backend || true

echo "[deploy] Health check..."
domain="${APP_DOMAIN:-}"
if [[ -n "$domain" ]]; then
  health_url="https://${domain}/api/health"
else
  health_url="http://localhost:8000/health"
  echo "[deploy] WARNING: APP_DOMAIN not set; checking backend directly (dev only)"
fi
curl -fsS "$health_url" || (echo "[deploy] Health check failed at $health_url" && exit 1)

echo "[deploy] OK"

