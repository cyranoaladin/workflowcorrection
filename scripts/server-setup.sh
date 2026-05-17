#!/usr/bin/env bash
# ============================================================
#  server-setup.sh — Installation complète sur 88.99.254.59
#  À exécuter UNE SEULE FOIS en tant que root sur le serveur.
#  Installe Docker, clone le projet, génère les secrets,
#  configure Caddy pour maths.labomaths.tn, et lance la stack.
# ============================================================
set -euo pipefail

REPO="https://github.com/cyranoaladin/workflowcorrection.git"
APP_DIR="/opt/math-correction"
DOMAIN="maths.labomaths.tn"
ACME_EMAIL="cyranoaladin@gmail.com"
STATIC_ROOT="/var/www/maths"   # Chemin du site statique existant

log() { echo -e "\n\033[1;36m[SETUP]\033[0m $*"; }
ok()  { echo -e "\033[1;32m  ✓\033[0m $*"; }
err() { echo -e "\033[1;31m  ✗\033[0m $*" >&2; exit 1; }

# ── 1. Pré-requis système ────────────────────────────────────
log "Mise à jour système..."
apt-get update -qq && apt-get upgrade -y -qq

log "Installation Docker..."
if ! command -v docker &>/dev/null; then
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
  ok "Docker installé"
else
  ok "Docker déjà présent ($(docker --version))"
fi

if ! docker compose version &>/dev/null; then
  apt-get install -y docker-compose-plugin
  ok "Docker Compose plugin installé"
else
  ok "Docker Compose déjà présent"
fi

# ── 2. Détection du site statique existant ──────────────────
log "Détection du site statique maths.labomaths.tn..."
if [[ ! -d "$STATIC_ROOT" ]]; then
  # Chercher où Caddy sert actuellement le site
  FOUND=$(find /var/www /srv /home -maxdepth 3 -name "index.html" 2>/dev/null | grep -i maths | head -1 || true)
  if [[ -n "$FOUND" ]]; then
    STATIC_ROOT="$(dirname "$FOUND")"
    ok "Site statique trouvé à : $STATIC_ROOT"
  else
    # Chercher dans la config Caddy existante
    CADDY_ROOT=$(grep -r "root \*" /etc/caddy/ 2>/dev/null | awk '{print $3}' | head -1 || true)
    if [[ -n "$CADDY_ROOT" ]]; then
      STATIC_ROOT="$CADDY_ROOT"
      ok "Root Caddy existant : $STATIC_ROOT"
    else
      log "⚠ Site statique introuvable automatiquement. Valeur par défaut : $STATIC_ROOT"
      log "  Si incorrect, éditer /etc/caddy/Caddyfile après installation."
    fi
  fi
fi

# ── 3. Clone / mise à jour du projet ────────────────────────
log "Installation du projet dans $APP_DIR..."
if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" pull origin main
  ok "Projet mis à jour depuis git"
else
  git clone "$REPO" "$APP_DIR"
  ok "Projet cloné"
fi

# ── 4. Génération des secrets ────────────────────────────────
log "Génération des secrets..."

ADMIN_API_TOKEN=$(openssl rand -hex 40)
JWT_SECRET=$(openssl rand -hex 40)
POSTGRES_PASSWORD=$(openssl rand -hex 24)

# Mot de passe Basic Auth Caddy (valeur fixe générée une fois)
CADDY_PLAIN_PASSWORD=$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)

# Hash bcrypt du mot de passe Caddy
CADDY_BCRYPT_RAW=$(docker run --rm caddy:2.8-alpine \
  caddy hash-password --plaintext "$CADDY_PLAIN_PASSWORD" 2>/dev/null)

# Échapper les $ pour docker-compose env files
CADDY_BASIC_AUTH_HASH=$(echo "$CADDY_BCRYPT_RAW" | sed 's/\$/\$\$/g')

ok "Secrets générés"

# ── 5. Création du fichier .env de production ────────────────
log "Création du .env de production..."

cat > "$APP_DIR/.env" << EOF
# ── Domain & TLS ────────────────────────────────────────────
APP_DOMAIN=${DOMAIN}
CADDY_ACME_EMAIL=${ACME_EMAIL}
CADDY_BASIC_AUTH_USER=admin
CADDY_BASIC_AUTH_HASH=${CADDY_BASIC_AUTH_HASH}

# ── Application ─────────────────────────────────────────────
APP_ENV=production
APP_NAME=math-correction-platform
APP_HOST=0.0.0.0
APP_PORT=8000
PUBLIC_API_BASE_URL=https://${DOMAIN}/correction/api
NEXT_PUBLIC_API_BASE_URL=https://${DOMAIN}/correction/api

# ── Database ─────────────────────────────────────────────────
POSTGRES_DB=correction_db
POSTGRES_USER=correction_user
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
DATABASE_URL=postgresql+psycopg2://correction_user:${POSTGRES_PASSWORD}@postgres:5432/correction_db

# ── Redis + Celery ───────────────────────────────────────────
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# ── Storage ──────────────────────────────────────────────────
STORAGE_BACKEND=local
LOCAL_STORAGE_PATH=/app/storage
MAX_UPLOAD_SIZE_MB=50
PDF_MAX_PAGES=50

# ── Security ─────────────────────────────────────────────────
ADMIN_API_TOKEN=${ADMIN_API_TOKEN}
JWT_SECRET=${JWT_SECRET}
ADMIN_EMAIL=${ACME_EMAIL}
ADMIN_PASSWORD=$(openssl rand -base64 16)
CORS_ALLOWED_ORIGINS=https://${DOMAIN}

# ── OCR / AI ─────────────────────────────────────────────────
OCR_ENABLE_PAID_CALLS=false
OCR_MAX_PAGES_PER_JOB=3
OCR_DEFAULT_IMAGE_TYPE=processed
MATHPIX_APP_ID=
MATHPIX_APP_KEY=
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=
AZURE_DOCUMENT_INTELLIGENCE_KEY=
OPENAI_API_KEY=
OPENAI_VISION_MODEL=gpt-4.1
OPENAI_GRADING_MODEL=gpt-4.1
OPENAI_AUDIT_MODEL=gpt-4.1
EOF

chmod 600 "$APP_DIR/.env"
ok ".env créé avec permissions 600"

# ── 6. Configuration Caddy ───────────────────────────────────
log "Configuration de Caddy pour ${DOMAIN}..."

# Détecter si Caddy est en service système ou en Docker
CADDY_MODE="system"
if systemctl is-active --quiet caddy 2>/dev/null; then
  CADDY_MODE="system"
  ok "Caddy détecté en service système"
elif docker ps 2>/dev/null | grep -q caddy; then
  CADDY_MODE="docker"
  ok "Caddy détecté en container Docker"
fi

# Remplacer le placeholder du chemin statique dans Caddyfile.labomaths
sed "s|/var/www/maths|${STATIC_ROOT}|g" "$APP_DIR/Caddyfile.labomaths" > /tmp/Caddyfile.new

if [[ "$CADDY_MODE" == "system" ]]; then
  # Caddy en service système
  cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.bak.$(date +%Y%m%d%H%M%S)
  ok "Backup Caddyfile existant sauvegardé"
  cp /tmp/Caddyfile.new /etc/caddy/Caddyfile
  # Injecter les variables d'env dans l'environnement systemd de Caddy
  mkdir -p /etc/systemd/system/caddy.service.d
  cat > /etc/systemd/system/caddy.service.d/override.conf << EOF2
[Service]
EnvironmentFile=${APP_DIR}/.env
EOF2
  systemctl daemon-reload
  systemctl reload caddy 2>/dev/null || systemctl restart caddy
  ok "Caddy système reconfiguré et rechargé"
fi

# ── 7. Ajout du réseau Docker partagé ───────────────────────
log "Création du réseau Docker partagé..."
docker network create math-correction-net 2>/dev/null || ok "Réseau déjà existant"

# ── 8. Lancement de la stack workflowcorrection ─────────────
log "Lancement de la stack Docker (intégration labomaths)..."
cd "$APP_DIR"
docker compose -f docker-compose.labomaths.yml --env-file .env pull 2>/dev/null || true
docker compose -f docker-compose.labomaths.yml --env-file .env up -d --build

ok "Stack démarrée (backend:8001, frontend:3001)"

# ── 9. Attendre que le backend soit prêt ────────────────────
log "Attente du démarrage du backend (max 90s)..."
for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8001/health &>/dev/null; then
    ok "Backend opérationnel sur :8001"
    break
  fi
  echo "  ... tentative $i/30"
  sleep 3
done

# ── 10. Affichage du résumé ──────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║          DÉPLOIEMENT TERMINÉ — INFORMATIONS IMPORTANTES      ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  URL publique  : https://${DOMAIN}/correction/          ║"
echo "║  Health check  : https://${DOMAIN}/correction/api/health║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  IDENTIFIANTS BASIC AUTH (à conserver précieusement)         ║"
echo "║  Utilisateur   : admin                                       ║"
echo "║  Mot de passe  : ${CADDY_PLAIN_PASSWORD}                    ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  Secrets stockés dans : ${APP_DIR}/.env (chmod 600)    ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  PROCHAINES ÉTAPES :                                         ║"
echo "║  1. Renseigner les clés OCR dans ${APP_DIR}/.env       ║"
echo "║  2. Redémarrer après ajout des clés :                        ║"
echo "║     cd ${APP_DIR}                                      ║"
echo "║     docker compose -f docker-compose.labomaths.yml           ║"
echo "║       --env-file .env up -d --build                          ║"
echo "╚══════════════════════════════════════════════════════════════╝"

# ── 10. Vérification finale ─────────────────────────────────
log "Smoke test final..."
sleep 5
curl -fsS "http://127.0.0.1:8001/health" && ok "Backend répond OK sur :8001" \
  || echo "⚠ Backend pas encore prêt — vérifier :"
  echo "   docker compose -f $APP_DIR/docker-compose.labomaths.yml logs backend"
