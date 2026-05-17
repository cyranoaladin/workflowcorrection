#!/usr/bin/env bash
# =============================================================
#  deploy_server.sh — Déploiement complet sur maths.labomaths.tn
#  À exécuter sur le serveur après connexion SSH :
#    ssh -i ~/.ssh/<KEY> alaeddine@maths.labomaths.tn
#    bash /opt/math-correction/scripts/deploy_server.sh
# =============================================================
set -euo pipefail

COMPOSE_FILE="docker-compose.labomaths.yml"
PROJECT_DIR="/opt/math-correction"

echo "=== [1/5] Pull du code depuis GitHub ==="
cd "$PROJECT_DIR"
git pull origin main

echo "=== [2/5] Rebuild frontend (no-cache) ==="
docker compose -f "$COMPOSE_FILE" build --no-cache frontend

echo "=== [3/5] Redémarrage du frontend ==="
docker compose -f "$COMPOSE_FILE" up -d frontend

echo "=== [4/5] Mise à jour Caddyfile ==="
cp "$PROJECT_DIR/Caddyfile.labomaths" /etc/caddy/Caddyfile
caddy validate --config /etc/caddy/Caddyfile && systemctl reload caddy || {
  echo "ERREUR: Caddyfile invalide — reload annulé"
  exit 1
}

echo "=== [5/5] Vérification ==="
sleep 3

echo -n "Port 80  : "; curl -s -o /dev/null -w "%{http_code}" http://maths.labomaths.tn/ || echo "KO"
echo -n "Port 443 : "; curl -sk -o /dev/null -w "%{http_code}" https://maths.labomaths.tn/ || echo "KO"
echo -n "/correction/ : "; curl -sk -o /dev/null -w "%{http_code}" https://maths.labomaths.tn/correction/ || echo "KO"
echo -n "/_next asset  : "; curl -sk -o /dev/null -w "%{http_code}" "https://maths.labomaths.tn/correction/_next/static/chunks/main-app.js" || echo "KO (normal si hash différent)"
echo -n "API health    : "; curl -sk https://maths.labomaths.tn/correction/api/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','?'))" 2>/dev/null || echo "KO"

echo ""
echo "=== Déploiement terminé ==="
docker compose -f "$COMPOSE_FILE" ps
