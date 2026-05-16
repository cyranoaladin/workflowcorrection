#!/usr/bin/env bash
set -euo pipefail

cd /opt/math-correction

if [[ ! -f ".env" ]]; then
  echo "[backup-db] Missing .env. Create it with: cp .env.example .env"
  exit 1
fi

set -a
# shellcheck disable=SC1091
source ./.env
set +a

ts="$(date -u +%Y%m%dT%H%M%SZ)"
out_dir="/opt/math-correction/backups"
mkdir -p "$out_dir"
out_file="$out_dir/postgres_${ts}.sql"

echo "[backup-db] Writing $out_file ..."
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" >"$out_file"
echo "[backup-db] Done."
