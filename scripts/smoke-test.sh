#!/usr/bin/env bash
set -euo pipefail

# Usage (production via Caddy):
#   APP_DOMAIN=workflow.example.com \
#   CADDY_BASIC_AUTH_USER=admin \
#   CADDY_BASIC_AUTH_PASS=your-plaintext-password \
#   ADMIN_API_TOKEN=<token> \
#   ./scripts/smoke-test.sh
#
# Usage (local direct backend, dev only):
#   ./scripts/smoke-test.sh http://localhost:8000

if [[ -n "${APP_DOMAIN:-}" ]]; then
  base="https://${APP_DOMAIN}"
else
  base="${1:-http://localhost:8000}"
fi

basic_user="${CADDY_BASIC_AUTH_USER:-}"
basic_pass="${CADDY_BASIC_AUTH_PASS:-}"
basic_args=()
if [[ -n "$basic_user" && -n "$basic_pass" ]]; then
  basic_args=(--user "${basic_user}:${basic_pass}")
fi

token="${ADMIN_API_TOKEN:-}"
auth_args=()
if [[ -n "$token" && -z "${APP_DOMAIN:-}" ]]; then
  auth_args=(-H "Authorization: Bearer $token")
fi

# In production (APP_DOMAIN set) Caddy exposes the API under /api/*.
# In local dev (direct backend) FastAPI serves routes at the root: /health, /exams …
if [[ -n "${APP_DOMAIN:-}" ]]; then
  api="$base/api"
else
  api="$base"
fi

echo "[smoke-test] Health (public): $api/health"
curl -fsS "$api/health" | sed 's/.*/[smoke-test] &/'

echo "[smoke-test] Health ready (public): $api/health/ready"
curl -fsS "$api/health/ready" | sed 's/.*/[smoke-test] &/'

echo "[smoke-test] Create exam..."
exam_json="$(curl -fsS -X POST "$api/exams" \
  "${basic_args[@]}" "${auth_args[@]}" \
  -H 'Content-Type: application/json' \
  -d '{"title":"Demo Exam","level":"test","session":"2026"}')"
echo "$exam_json"

echo "[smoke-test] List exams..."
curl -fsS "$api/exams" "${basic_args[@]}" "${auth_args[@]}" | head -c 500; echo

echo "[smoke-test] OK (upload/process steps require PDF files)."
