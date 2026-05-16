#!/usr/bin/env bash
set -euo pipefail

echo "[init-server] Starting..."

if [[ $EUID -ne 0 ]]; then
  echo "[init-server] Please run as root."
  exit 1
fi

echo "[init-server] OS:"
uname -a || true

echo "[init-server] Updating apt indexes..."
apt-get update -y

if ! command -v docker >/dev/null 2>&1; then
  echo "[init-server] Docker not found. Installing docker.io (simple path)..."
  apt-get install -y docker.io
  systemctl enable --now docker
else
  echo "[init-server] Docker already installed: $(docker --version)"
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "[init-server] Docker Compose plugin not found."
  echo "[init-server] On Ubuntu 24.04, try: apt-get install -y docker-compose-plugin"
else
  echo "[init-server] Docker Compose: $(docker compose version)"
fi

echo "[init-server] Creating /opt/math-correction and storage..."
mkdir -p /opt/math-correction
mkdir -p /opt/math-correction/storage/{exams,copies,pages,zones,transcriptions,reports}

echo "[init-server] Checking ports (22/8000)..."
if ss -ltn | grep -q ':8000'; then
  echo "[init-server] WARNING: port 8000 already in use."
else
  echo "[init-server] OK: port 8000 seems free."
fi

echo
echo "[init-server] Next steps:"
echo "  1) Put project files into /opt/math-correction"
echo "  2) cd /opt/math-correction && cp .env.example .env"
echo "  3) Edit .env (passwords/secrets)"
echo "  4) docker compose up -d --build"
echo "  5) curl http://localhost:8000/health"

