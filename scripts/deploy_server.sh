#!/usr/bin/env bash
# =============================================================
#  deploy_server.sh — Déploiement complet sur maths.labomaths.tn
#
#  Serveur : Hetzner dédié 88.99.254.59
#  Reverse proxy : Nginx système
#  Backend  → 127.0.0.1:8010
#  Frontend → 127.0.0.1:3011
#
#  Usage :
#    ssh root@88.99.254.59
#    cd /opt/math-correction && bash scripts/deploy_server.sh
# =============================================================
set -euo pipefail

COMPOSE_FILE="docker-compose.labomaths.yml"
PROJECT_DIR="/opt/math-correction"

cd "$PROJECT_DIR"

echo "=== [1/10] Pull du code depuis GitHub ==="
git stash --include-untracked 2>/dev/null || true
git pull origin main
git stash pop 2>/dev/null || true

echo "=== [2/10] Regénérer package-lock.json si nécessaire ==="
docker run --rm -v "$(pwd)/frontend:/app" -w /app node:20-alpine sh -c \
  'npm install --package-lock-only 2>&1 | tail -3'

echo "=== [3/10] Sauvegarde DB (filet de sécurité) ==="
BACKUP_DIR="$PROJECT_DIR/backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
if docker compose -f "$COMPOSE_FILE" ps postgres --status running -q 2>/dev/null | grep -q .; then
  docker compose -f "$COMPOSE_FILE" exec -T postgres \
    sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
    > "$BACKUP_DIR/db_pre_deploy.sql" 2>/dev/null \
    && echo "  ✓ Backup DB → $BACKUP_DIR/db_pre_deploy.sql" \
    || echo "  ⚠ pg_dump skipped (container not ready or first deploy)"
else
  echo "  ⚠ Postgres not running, skipping backup"
fi

echo "=== [4/10] Arrêt et nettoyage des anciens containers ==="
docker compose -f "$COMPOSE_FILE" down --remove-orphans || true
docker container prune -f 2>/dev/null || true

echo "=== [5/10] Rebuild des images applicatives (no-cache) ==="
docker compose -f "$COMPOSE_FILE" build --no-cache backend worker frontend

echo "=== [6/10] Démarrage des dépendances ==="
docker compose -f "$COMPOSE_FILE" up -d postgres redis
echo "  Attente healthcheck postgres…"
docker compose -f "$COMPOSE_FILE" exec -T postgres sh -c \
  'until pg_isready -U ${POSTGRES_USER:-postgres}; do sleep 1; done'

echo "=== [7/10] Migration base de données ==="
docker compose -f "$COMPOSE_FILE" run --rm backend alembic upgrade head

echo "=== [8/10] Démarrage de tous les services ==="
docker compose -f "$COMPOSE_FILE" up -d

echo "=== [9/10] Vérification Nginx ==="
nginx -t && systemctl reload nginx || echo "⚠ Nginx reload skipped"

echo "=== [10/10] Tests de santé ==="
sleep 5

FAIL=0
check() {
  local label="$1" url="$2" expect="$3"
  code=$(curl -sk --max-time 10 -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
  if [ "$code" = "$expect" ]; then
    echo "  ✓ $label → $code"
  else
    echo "  ✗ $label → $code (attendu $expect)"
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
    echo "  ✓ CSS MIME type → $ctype"
  else
    echo "  ✗ CSS MIME type → $ctype (attendu text/css)"
    FAIL=1
  fi
fi

echo ""
docker compose -f "$COMPOSE_FILE" ps
echo ""
if [ "$FAIL" -eq 0 ]; then
  echo "✅ Déploiement terminé — tous les tests OK"
else
  echo "⚠️  Déploiement terminé — certains tests ont échoué"
  exit 1
fi
