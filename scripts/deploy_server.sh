#!/usr/bin/env bash
# =============================================================
#  deploy_server.sh — Deploiement complet sur maths.labomaths.tn
#
#  Serveur : Hetzner dedie 88.99.254.59
#  Reverse proxy : Nginx systeme
#  Backend  -> 127.0.0.1:8010
#  Frontend -> 127.0.0.1:3011
#
#  Usage :
#    ssh root@88.99.254.59
#    cd /opt/math-correction && bash scripts/deploy_server.sh
# =============================================================
set -euo pipefail

COMPOSE_FILE="docker-compose.labomaths.yml"
PROJECT_DIR="/opt/math-correction"

cd "$PROJECT_DIR"

echo "=== [1/11] Pull du code depuis GitHub ==="
git stash --include-untracked 2>/dev/null || true
git pull origin main
git stash pop 2>/dev/null || true

echo "=== [2/11] Regenerer package-lock.json si necessaire ==="
docker run --rm -v "$(pwd)/frontend:/app" -w /app node:20-alpine sh -c \
  'npm install --package-lock-only 2>&1 | tail -3'

echo "=== [3/11] Sauvegarde DB (filet de securite) ==="
BACKUP_DIR="$PROJECT_DIR/backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
if docker compose -f "$COMPOSE_FILE" ps postgres --status running -q 2>/dev/null | grep -q .; then
  docker compose -f "$COMPOSE_FILE" exec -T postgres \
    sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
    > "$BACKUP_DIR/db_pre_deploy.sql" 2>/dev/null \
    && echo "  OK Backup DB -> $BACKUP_DIR/db_pre_deploy.sql" \
    || echo "  WARN pg_dump skipped (container not ready or first deploy)"
else
  echo "  WARN Postgres not running, skipping backup"
fi

echo "=== [4/11] Build des images applicatives (sans arreter les services) ==="
docker compose -f "$COMPOSE_FILE" build --no-cache backend worker frontend

echo "=== [5/11] Demarrage des dependances ==="
docker compose -f "$COMPOSE_FILE" up -d postgres redis
echo "  Attente healthcheck postgres..."
docker compose -f "$COMPOSE_FILE" exec -T postgres sh -c \
  'until pg_isready -U ${POSTGRES_USER:-postgres}; do sleep 1; done'

echo "=== [6/11] Migration base de donnees ==="
docker compose -f "$COMPOSE_FILE" run --rm backend alembic upgrade head

echo "=== [7/11] Redemarrage progressif des services ==="
docker compose -f "$COMPOSE_FILE" up -d --no-deps backend worker frontend

echo "=== [8/11] Deploiement config Nginx depuis le repo ==="
if [ -f "$PROJECT_DIR/nginx/maths.labomaths.tn.conf" ]; then
  # Substitute the admin token placeholder
  ADMIN_TOKEN=$(grep "^ADMIN_API_TOKEN=" "$PROJECT_DIR/.env" | cut -d= -f2 | tr -d "\"'")
  sed "s/%%ADMIN_API_TOKEN%%/$ADMIN_TOKEN/g" \
    "$PROJECT_DIR/nginx/maths.labomaths.tn.conf" \
    > /etc/nginx/sites-enabled/maths.labomaths.tn
  echo "  OK Nginx config deployed from repo"
fi

echo "=== [9/11] Verification Nginx ==="
nginx -t && systemctl reload nginx || echo "WARN Nginx reload skipped"

echo "=== [10/11] Attente sante backend (max 60s) ==="
for i in $(seq 1 30); do
  if curl -fsS http://localhost:8010/health/ready >/dev/null 2>&1; then
    echo "  OK Backend healthy apres $((i * 2))s"
    break
  fi
  if [ "$i" = "30" ]; then
    echo "  FAIL Backend pas healthy apres 60s"
    echo "  Logs backend:"
    docker logs math-correction-backend-1 --tail=20 2>&1 || true
    exit 1
  fi
  sleep 2
done

# Verify all containers are running
RUNNING=$(docker compose -f "$COMPOSE_FILE" ps --services --filter "status=running" 2>/dev/null | wc -l)
EXPECTED=5
if [ "$RUNNING" -lt "$EXPECTED" ]; then
  echo "  WARN Only $RUNNING/$EXPECTED containers running, restarting..."
  docker compose -f "$COMPOSE_FILE" up -d
  sleep 5
fi

echo "=== [11/11] Tests de sante ==="

FAIL=0
check() {
  local label="$1" url="$2" expect="$3"
  code=$(curl -sk --max-time 10 -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
  if [ "$code" = "$expect" ]; then
    echo "  OK $label -> $code"
  else
    echo "  FAIL $label -> $code (attendu $expect)"
    FAIL=1
  fi
}

echo ""
check "Site statique"           "https://maths.labomaths.tn/"                           "200"
check "/correction/ (auth)"     "https://maths.labomaths.tn/correction/"                "401"
check "API health"              "https://maths.labomaths.tn/correction/api/health"       "200"
check "Backend readiness"       "http://127.0.0.1:8010/health/ready"                     "200"
check "Frontend local"          "http://127.0.0.1:3011/"                                 "200"

# Test _next asset MIME type
CSS_URL=$(curl -s http://127.0.0.1:3011/ | grep -oP '/correction/_next/static/[^"]+\.css' | head -1)
if [ -n "$CSS_URL" ]; then
  ctype=$(curl -sk --max-time 5 -o /dev/null -w "%{content_type}" "https://maths.labomaths.tn$CSS_URL" 2>/dev/null)
  if echo "$ctype" | grep -q "text/css"; then
    echo "  OK CSS MIME type -> $ctype"
  else
    echo "  FAIL CSS MIME type -> $ctype (attendu text/css)"
    FAIL=1
  fi
fi

echo ""
docker compose -f "$COMPOSE_FILE" ps
echo ""
if [ "$FAIL" -eq 0 ]; then
  echo "Deploiement termine — tous les tests OK"
else
  echo "Deploiement termine — certains tests ont echoue"
  exit 1
fi
