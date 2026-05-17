#!/usr/bin/env bash
# ============================================================
# audit_live.sh — Audit complet de l'application déployée
# Usage: bash audit_live.sh [BASE_URL] [ADMIN_TOKEN]
# Ex  : bash audit_live.sh https://maths.labomaths.tn/api TOKEN
# ============================================================
set -euo pipefail

BASE_URL="${1:-https://maths.labomaths.tn/api}"
TOKEN="${2:-}"
BASIC_AUTH_USER="${3:-admin}"
BASIC_AUTH_PASS="${4:-}"

PASS=0; FAIL=0; WARN=0
RESULTS=()

# ─── helpers ─────────────────────────────────────────────────────────────────
green()  { printf "\033[32m✓ %s\033[0m\n" "$*"; }
red()    { printf "\033[31m✗ %s\033[0m\n" "$*"; }
yellow() { printf "\033[33m⚠ %s\033[0m\n" "$*"; }
blue()   { printf "\033[34m» %s\033[0m\n" "$*"; }

check() {
    local label="$1"; local expected_status="$2"; shift 2
    local resp
    resp=$(curl -s -o /tmp/audit_body -w "%{http_code}" "$@")
    local body; body=$(cat /tmp/audit_body)

    if [[ "$resp" == "$expected_status" ]]; then
        green "$label (HTTP $resp)"
        PASS=$((PASS+1))
        RESULTS+=("PASS: $label")
    else
        red "$label — expected $expected_status, got $resp"
        FAIL=$((FAIL+1))
        RESULTS+=("FAIL: $label — expected $expected_status, got $resp — body: $(echo "$body" | head -c 200)")
    fi
    echo "$body" > /tmp/audit_last_body
}

check_contains() {
    local label="$1"; local needle="$2"; shift 2
    curl -s -o /tmp/audit_body "$@"
    local body; body=$(cat /tmp/audit_body)
    if echo "$body" | grep -q "$needle"; then
        green "$label (contains '$needle')"
        PASS=$((PASS+1))
        RESULTS+=("PASS: $label")
    else
        red "$label — response does not contain '$needle'"
        FAIL=$((FAIL+1))
        RESULTS+=("FAIL: $label — missing '$needle' — body: $(echo "$body" | head -c 300)")
    fi
}

warn_check() {
    local label="$1"; local expected_status="$2"; shift 2
    local resp
    resp=$(curl -s -o /tmp/audit_body -w "%{http_code}" "$@")
    if [[ "$resp" == "$expected_status" ]]; then
        green "$label (HTTP $resp)"
        PASS=$((PASS+1))
    else
        yellow "$label — expected $expected_status, got $resp (non-blocking)"
        WARN=$((WARN+1))
        RESULTS+=("WARN: $label — expected $expected_status, got $resp")
    fi
}

AUTH_HEADERS=(-H "Authorization: Bearer $TOKEN")
if [[ -n "$BASIC_AUTH_PASS" ]]; then
    CURL_AUTH=(-u "$BASIC_AUTH_USER:$BASIC_AUTH_PASS")
else
    CURL_AUTH=()
fi

# ─── 1. Health ────────────────────────────────────────────────────────────────
blue "=== 1. HEALTH ==="
check "GET /health" "200" "${CURL_AUTH[@]}" "$BASE_URL/health"
check "GET /health/live" "200" "${CURL_AUTH[@]}" "$BASE_URL/health/live"
check "GET /health/ready" "200" "${CURL_AUTH[@]}" "$BASE_URL/health/ready"
check_contains "DB healthy" '"database":"ok"' "${CURL_AUTH[@]}" "$BASE_URL/health/ready"
check_contains "Redis healthy" '"redis":"ok"' "${CURL_AUTH[@]}" "$BASE_URL/health/ready"
check_contains "Storage healthy" '"storage":"ok"' "${CURL_AUTH[@]}" "$BASE_URL/health/ready"

# ─── 2. Auth ──────────────────────────────────────────────────────────────────
blue "=== 2. AUTHENTIFICATION ==="
if [[ -n "$TOKEN" ]]; then
    check "GET /exams with token → 200" "200" "${CURL_AUTH[@]}" "${AUTH_HEADERS[@]}" "$BASE_URL/exams"
    check "GET /exams without token → 401" "401" "${CURL_AUTH[@]}" "$BASE_URL/exams"
    check "GET /exams wrong token → 401" "401" "${CURL_AUTH[@]}" -H "Authorization: Bearer wrong" "$BASE_URL/exams"
else
    yellow "No ADMIN_TOKEN provided — skipping auth tests"
    WARN=$((WARN+1))
fi

# ─── 3. API routes inventory ──────────────────────────────────────────────────
blue "=== 3. ROUTES API ==="
OPENAPI_RESP=$(curl -s "${CURL_AUTH[@]}" "${AUTH_HEADERS[@]}" "$BASE_URL/openapi.json")
EXPECTED_ROUTES=(
    "GET /health"
    "POST /exams"
    "GET /exams"
    "GET /exams/{exam_id}"
    "PATCH /exams/{exam_id}"
    "POST /exams/{exam_id}/files"
    "POST /exams/{exam_id}/rubric-json"
    "POST /exams/{exam_id}/students/csv"
    "GET /exams/{exam_id}/bilan"
    "POST /copies"
    "GET /copies"
    "GET /copies/{copy_id}"
    "POST /copies/{copy_id}/process"
    "POST /copies/{copy_id}/grade"
    "POST /copies/{copy_id}/grade-async"
    "GET /copies/{copy_id}/report"
    "GET /copies/{copy_id}/pages"
    "GET /copies/{copy_id}/status"
    "GET /copies/{copy_id}/transcriptions"
    "POST /copies/{copy_id}/ocr"
    "GET /pages/{page_id}/image"
    "GET /pages/{page_id}/transcriptions"
    "POST /pages/{page_id}/ocr/azure"
    "POST /pages/{page_id}/ocr/mathpix"
    "POST /pages/{page_id}/ocr/openai-vision"
    "POST /pages/{page_id}/ocr/fuse"
    "PATCH /corrections/{correction_id}/validate"
    "GET /integrations/status"
)

for route in "${EXPECTED_ROUTES[@]}"; do
    METHOD=$(echo "$route" | cut -d' ' -f1 | tr '[:upper:]' '[:lower:]')
    PATH_PART=$(echo "$route" | cut -d' ' -f2)
    # Strip path params for JSON search
    PATH_CLEAN=$(echo "$PATH_PART" | sed 's/{[^}]*}/\{[^}]*\}/g')
    if echo "$OPENAPI_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); paths=d.get('paths',{}); exits=any('$METHOD' in methods for p,methods in paths.items() if '$PATH_PART'==p); sys.exit(0 if exits else 1)" 2>/dev/null; then
        green "Route présente: $METHOD $PATH_PART"
        PASS=$((PASS+1))
    else
        red "Route MANQUANTE: $METHOD $PATH_PART"
        FAIL=$((FAIL+1))
        RESULTS+=("FAIL: Route manquante $METHOD $PATH_PART")
    fi
done

# ─── 4. Integrations / OCR / LLM ─────────────────────────────────────────────
blue "=== 4. INTÉGRATIONS OCR & LLM ==="
INTEG=$(curl -s "${CURL_AUTH[@]}" "${AUTH_HEADERS[@]}" "$BASE_URL/integrations/status")
echo "Réponse intégrations: $INTEG"

for service in mathpix azure_document_intelligence openai; do
    if echo "$INTEG" | python3 -c "import sys,json; d=json.load(sys.stdin); s=d.get('$service',{}); configured=s.get('configured',False); sys.exit(0 if configured else 1)" 2>/dev/null; then
        green "Intégration configurée: $service"
        PASS=$((PASS+1))
    else
        yellow "Intégration NON configurée: $service (clé API manquante)"
        WARN=$((WARN+1))
        RESULTS+=("WARN: Intégration $service non configurée")
    fi
done

# ─── 5. CRUD fonctionnel ──────────────────────────────────────────────────────
blue "=== 5. CRUD FONCTIONNEL ==="

# Create exam
EXAM_RESP=$(curl -s "${CURL_AUTH[@]}" "${AUTH_HEADERS[@]}" -X POST \
    -H "Content-Type: application/json" \
    -d '{"title":"audit-test-exam","level":"TS","session":"2026"}' \
    "$BASE_URL/exams")
EXAM_ID=$(echo "$EXAM_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || true)

if [[ -n "$EXAM_ID" ]]; then
    green "POST /exams → exam créé: $EXAM_ID"
    PASS=$((PASS+1))

    # Set rubric
    RUBRIC_RESP=$(curl -s -o /tmp/audit_body -w "%{http_code}" "${CURL_AUTH[@]}" "${AUTH_HEADERS[@]}" \
        -X POST -H "Content-Type: application/json" \
        -d '{"questions":[{"id":"Q1","label":"Test","points_max":4,"criteria":["ok"]}]}' \
        "$BASE_URL/exams/$EXAM_ID/rubric-json")
    if [[ "$RUBRIC_RESP" == "200" ]]; then
        green "POST /exams/{id}/rubric-json → OK"
        PASS=$((PASS+1))
    else
        red "POST /exams/{id}/rubric-json → HTTP $RUBRIC_RESP"
        FAIL=$((FAIL+1))
    fi

    # Get exam
    check "GET /exams/{id}" "200" "${CURL_AUTH[@]}" "${AUTH_HEADERS[@]}" "$BASE_URL/exams/$EXAM_ID"

    # Bilan (empty)
    check "GET /exams/{id}/bilan (vide)" "200" "${CURL_AUTH[@]}" "${AUTH_HEADERS[@]}" "$BASE_URL/exams/$EXAM_ID/bilan"

    # CSV import
    CSV_DATA="student_name,copy_code
Alice Martin,A01
Bob Dupont,A02"
    CSV_RESP=$(curl -s -o /tmp/audit_body -w "%{http_code}" "${CURL_AUTH[@]}" "${AUTH_HEADERS[@]}" \
        -X POST -F "file=@-;filename=students.csv;type=text/csv" \
        "$BASE_URL/exams/$EXAM_ID/students/csv" <<< "$CSV_DATA")
    if [[ "$CSV_RESP" == "200" ]]; then
        CREATED=$(python3 -c "import json; d=json.load(open('/tmp/audit_body')); print(d.get('created',0))" 2>/dev/null || echo "0")
        green "POST /exams/{id}/students/csv → $CREATED élèves créés"
        PASS=$((PASS+1))
    else
        red "POST /exams/{id}/students/csv → HTTP $CSV_RESP"
        FAIL=$((FAIL+1))
    fi

    # List copies
    check "GET /copies?exam_id" "200" "${CURL_AUTH[@]}" "${AUTH_HEADERS[@]}" "$BASE_URL/copies?exam_id=$EXAM_ID"

    # Cleanup
    echo "  (Note: l'exam de test $EXAM_ID reste en DB — supprimez manuellement si besoin)"
else
    red "POST /exams → impossible de créer un examen"
    FAIL=$((FAIL+1))
fi

# ─── 6. Sécurité TLS & headers ───────────────────────────────────────────────
blue "=== 6. SÉCURITÉ TLS & HEADERS ==="
if [[ "$BASE_URL" == https://* ]]; then
    TLS_RESP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$BASE_URL/health" 2>/dev/null || echo "000")
    if [[ "$TLS_RESP" == "200" ]]; then
        green "TLS HTTPS → OK"
        PASS=$((PASS+1))
    else
        red "TLS HTTPS → HTTP $TLS_RESP"
        FAIL=$((FAIL+1))
    fi

    # Check HSTS
    HEADERS=$(curl -sI "${CURL_AUTH[@]}" "${AUTH_HEADERS[@]}" "$BASE_URL/health" 2>/dev/null)
    if echo "$HEADERS" | grep -qi "strict-transport-security"; then
        green "HSTS header présent"
        PASS=$((PASS+1))
    else
        yellow "HSTS header absent"
        WARN=$((WARN+1))
    fi
else
    yellow "BASE_URL non HTTPS — skip TLS checks"
    WARN=$((WARN+1))
fi

# ─── 7. Basic Auth Nginx ──────────────────────────────────────────────────────
blue "=== 7. BASIC AUTH NGINX ==="
if [[ -n "$BASIC_AUTH_PASS" ]]; then
    NOAUTH=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${AUTH_HEADERS[@]}" "$BASE_URL/health" 2>/dev/null || echo "000")
    if [[ "$NOAUTH" == "401" ]]; then
        green "Basic Auth Nginx protège le path → 401 sans credentials"
        PASS=$((PASS+1))
    else
        yellow "Basic Auth Nginx non détecté sur ce path (HTTP $NOAUTH)"
        WARN=$((WARN+1))
    fi
else
    yellow "BASIC_AUTH_PASS non fourni — skip Basic Auth check"
    WARN=$((WARN+1))
fi

# ─── 8. Docker containers ─────────────────────────────────────────────────────
blue "=== 8. DOCKER CONTAINERS ==="
if command -v docker &>/dev/null; then
    for svc in backend worker frontend postgres redis; do
        if docker ps --format "{{.Names}}" 2>/dev/null | grep -q "$svc"; then
            green "Container $svc → running"
            PASS=$((PASS+1))
        else
            yellow "Container $svc → non trouvé (run local?)"
            WARN=$((WARN+1))
        fi
    done
else
    yellow "docker non disponible — skip container checks"
    WARN=$((WARN+1))
fi

# ─── RÉSUMÉ ───────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════"
blue "RÉSUMÉ AUDIT"
echo "────────────────────────────────────────────────────────"
green "PASS : $PASS"
[[ $WARN -gt 0 ]] && yellow "WARN : $WARN"
[[ $FAIL -gt 0 ]] && red  "FAIL : $FAIL"
echo "════════════════════════════════════════════════════════"

if [[ $FAIL -gt 0 ]]; then
    echo ""
    red "ÉCHECS DÉTECTÉS :"
    for r in "${RESULTS[@]}"; do
        if [[ "$r" == FAIL* ]]; then echo "  $r"; fi
    done
fi

if [[ $WARN -gt 0 ]]; then
    echo ""
    yellow "AVERTISSEMENTS :"
    for r in "${RESULTS[@]}"; do
        if [[ "$r" == WARN* ]]; then echo "  $r"; fi
    done
fi

echo ""
if [[ $FAIL -eq 0 ]]; then
    green "Audit terminé — aucun échec critique"
    exit 0
else
    red "Audit terminé — $FAIL échec(s) critique(s)"
    exit 1
fi
