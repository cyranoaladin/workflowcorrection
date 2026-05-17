#!/usr/bin/env bash
# ============================================================
#  server-setup.sh — Installation complète sur 88.99.254.59
#  À exécuter UNE SEULE FOIS en tant que root sur le serveur.
#
#  Architecture réelle du serveur :
#    - Nginx gère 80/443 avec Let's Encrypt (certbot)
#    - maths.labomaths.tn sert /var/www/maths en statique
#    - Ce script ajoute /correction/ → workflowcorrection
#      (backend:127.0.0.1:8010, frontend:127.0.0.1:3010)
#    - Pas de Caddy — on reste sur Nginx
# ============================================================
set -euo pipefail

REPO="https://github.com/cyranoaladin/workflowcorrection.git"
APP_DIR="/opt/math-correction"
DOMAIN="maths.labomaths.tn"
ACME_EMAIL="cyranoaladin@gmail.com"
BACKEND_PORT="8010"   # Port interne backend (évite conflits avec apps existantes)
FRONTEND_PORT="3010"  # Port interne frontend

log() { echo -e "\n\033[1;36m[SETUP]\033[0m $*"; }
ok()  { echo -e "\033[1;32m  ✓\033[0m $*"; }
err() { echo -e "\033[1;31m  ✗\033[0m $*" >&2; exit 1; }

# ── 1. Docker (déjà installé, vérification) ─────────────────
log "Vérification Docker..."
docker --version || err "Docker absent — installer manuellement"
ok "Docker présent ($(docker --version))"

if ! docker compose version &>/dev/null; then
  apt-get install -y docker-compose-plugin
  ok "Docker Compose plugin installé"
else
  ok "Docker Compose présent"
fi

# ── 2. Clone / mise à jour du projet ────────────────────────
log "Installation du projet dans $APP_DIR..."
if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" pull origin main
  ok "Projet mis à jour depuis git"
else
  apt-get install -y git 2>/dev/null || true
  git clone "$REPO" "$APP_DIR"
  ok "Projet cloné"
fi

# ── 3. Génération des secrets ────────────────────────────────
log "Génération des secrets..."

ADMIN_API_TOKEN=$(openssl rand -hex 40)
JWT_SECRET=$(openssl rand -hex 40)
POSTGRES_PASSWORD=$(openssl rand -hex 24)
BASIC_AUTH_PASSWORD=$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)

# Hash bcrypt du mot de passe Basic Auth via htpasswd (nginx)
if command -v htpasswd &>/dev/null; then
  BASIC_AUTH_HASH=$(htpasswd -nbB admin "$BASIC_AUTH_PASSWORD" | cut -d: -f2)
else
  apt-get install -y apache2-utils -qq
  BASIC_AUTH_HASH=$(htpasswd -nbB admin "$BASIC_AUTH_PASSWORD" | cut -d: -f2)
fi

# Fichier htpasswd pour nginx
mkdir -p /etc/nginx/auth
echo "admin:${BASIC_AUTH_HASH}" > /etc/nginx/auth/correction.htpasswd
chmod 640 /etc/nginx/auth/correction.htpasswd
chown root:www-data /etc/nginx/auth/correction.htpasswd

ok "Secrets générés"

# ── 4. Création du fichier .env de production ────────────────
log "Création du .env de production..."

cat > "$APP_DIR/.env" << ENVEOF
# ── Domain ───────────────────────────────────────────────────
APP_DOMAIN=${DOMAIN}

# ── Application ──────────────────────────────────────────────
APP_ENV=production
APP_NAME=math-correction-platform
APP_HOST=0.0.0.0
APP_PORT=8000
PUBLIC_API_BASE_URL=https://${DOMAIN}/correction/api
NEXT_PUBLIC_API_BASE_URL=https://${DOMAIN}/correction/api

# ── Database ──────────────────────────────────────────────────
POSTGRES_DB=correction_db
POSTGRES_USER=correction_user
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
DATABASE_URL=postgresql+psycopg2://correction_user:${POSTGRES_PASSWORD}@postgres:5432/correction_db

# ── Redis + Celery ────────────────────────────────────────────
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# ── Storage ───────────────────────────────────────────────────
STORAGE_BACKEND=local
LOCAL_STORAGE_PATH=/app/storage
MAX_UPLOAD_SIZE_MB=50
PDF_MAX_PAGES=50

# ── Security ──────────────────────────────────────────────────
ADMIN_API_TOKEN=${ADMIN_API_TOKEN}
JWT_SECRET=${JWT_SECRET}
ADMIN_EMAIL=${ACME_EMAIL}
CORS_ALLOWED_ORIGINS=https://${DOMAIN}

# ── OCR / AI ──────────────────────────────────────────────────
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
ENVEOF

chmod 600 "$APP_DIR/.env"
ok ".env créé (chmod 600)"

# ── 5. Mise à jour docker-compose.labomaths.yml avec les bons ports ──
log "Configuration des ports Docker (backend:${BACKEND_PORT}, frontend:${FRONTEND_PORT})..."
sed -i "s|127.0.0.1:8001:8000|127.0.0.1:${BACKEND_PORT}:8000|g" "$APP_DIR/docker-compose.labomaths.yml"
sed -i "s|127.0.0.1:3001:3000|127.0.0.1:${FRONTEND_PORT}:3000|g" "$APP_DIR/docker-compose.labomaths.yml"
ok "Ports configurés"

# ── 6. Configuration Nginx — ajout de /correction/ ──────────
log "Configuration Nginx pour /correction/..."

NGINX_CONF="/etc/nginx/sites-available/maths.labomaths.tn"
if [[ ! -f "$NGINX_CONF" ]]; then
  NGINX_CONF=$(grep -rl "server_name maths.labomaths.tn" /etc/nginx/sites-available/ /etc/nginx/conf.d/ 2>/dev/null | head -1 || true)
  [[ -z "$NGINX_CONF" ]] && err "Impossible de trouver la config Nginx pour maths.labomaths.tn"
fi

# Backup
cp "$NGINX_CONF" "${NGINX_CONF}.bak.$(date +%Y%m%d%H%M%S)"
ok "Backup Nginx sauvegardé : ${NGINX_CONF}.bak.*"

# Vérifier si /correction/ est déjà configuré
if grep -q "location /correction/" "$NGINX_CONF"; then
  ok "Location /correction/ déjà présente dans Nginx — skip"
else
  # Injerer avant la dernière accolade fermante du bloc server 443
  # Insertion avant le bloc "# Default" ou avant la dernière location /
  CORRECTION_BLOCK="
    # ── Correction workflow (/correction/) ───────────────────
    # Basic Auth protection
    location /correction/api/health {
        proxy_pass http://127.0.0.1:${BACKEND_PORT}/health;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /correction/api/ {
        auth_basic \"Correction — Accès restreint\";
        auth_basic_user_file /etc/nginx/auth/correction.htpasswd;
        proxy_pass http://127.0.0.1:${BACKEND_PORT}/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Authorization \"Bearer ${ADMIN_API_TOKEN}\";
        client_max_body_size 50M;
        proxy_read_timeout 300s;
    }

    location /correction/ {
        auth_basic \"Correction — Accès restreint\";
        auth_basic_user_file /etc/nginx/auth/correction.htpasswd;
        proxy_pass http://127.0.0.1:${FRONTEND_PORT}/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \"upgrade\";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400;
    }
"
  # Insérer avant "# Default" ou avant la dernière "location /"
  if grep -q "# Default" "$NGINX_CONF"; then
    sed -i "s|# Default|${CORRECTION_BLOCK}\n    # Default|" "$NGINX_CONF"
  else
    # Insérer avant la dernière accolade fermante
    sed -i "$ s|}|${CORRECTION_BLOCK}\n}|" "$NGINX_CONF"
  fi
  ok "Bloc /correction/ injecté dans Nginx"
fi

# Test syntaxe Nginx
nginx -t && ok "Syntaxe Nginx valide" || err "Erreur syntaxe Nginx — vérifier $NGINX_CONF"
systemctl reload nginx
ok "Nginx rechargé"

# ── 7. Lancement de la stack Docker ─────────────────────────
log "Lancement de la stack Docker..."
cd "$APP_DIR"
docker compose -f docker-compose.labomaths.yml --env-file .env up -d --build
ok "Stack démarrée"

# ── 8. Attente backend ───────────────────────────────────────
log "Attente du backend (max 90s)..."
for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${BACKEND_PORT}/health" &>/dev/null; then
    ok "Backend opérationnel sur :${BACKEND_PORT}"
    break
  fi
  echo "  ... tentative $i/30"
  sleep 3
done

# ── 9. Smoke test ────────────────────────────────────────────
log "Smoke test..."
sleep 3
HTTP=$(curl -o /dev/null -sw "%{http_code}" "http://127.0.0.1:${BACKEND_PORT}/health" 2>/dev/null || echo "000")
[[ "$HTTP" == "200" ]] && ok "Backend health: 200 OK" || echo "⚠ Backend health: $HTTP (peut encore démarrer)"

# ── 10. Résumé ───────────────────────────────────────────────
echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║         DÉPLOIEMENT TERMINÉ — INFORMATIONS IMPORTANTES        ║"
echo "╠═══════════════════════════════════════════════════════════════╣"
echo "║  URL publique   : https://${DOMAIN}/correction/         ║"
echo "║  Health check   : https://${DOMAIN}/correction/api/health║"
echo "╠═══════════════════════════════════════════════════════════════╣"
echo "║  IDENTIFIANTS BASIC AUTH                                      ║"
echo "║  Utilisateur    : admin                                       ║"
echo "║  Mot de passe   : ${BASIC_AUTH_PASSWORD}                     ║"
echo "╠═══════════════════════════════════════════════════════════════╣"
echo "║  Secrets dans   : ${APP_DIR}/.env (chmod 600)          ║"
echo "╠═══════════════════════════════════════════════════════════════╣"
echo "║  PROCHAINE ÉTAPE : ajouter les clés OCR dans .env puis :      ║"
echo "║    cd ${APP_DIR}                                        ║"
echo "║    docker compose -f docker-compose.labomaths.yml \\           ║"
echo "║      --env-file .env up -d --build                            ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
