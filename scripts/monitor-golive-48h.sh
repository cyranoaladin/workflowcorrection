#!/usr/bin/env bash
# Go-live 48h monitoring — runs hourly via cron.
# Uses set -eu but NOT pipefail to avoid SIGPIPE exits from head/tail.
set -eu
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
LOG=/var/log/wc-golive-monitor.log

_grep_errors() {
  local out
  out=$(docker logs "$1" --since 1h 2>&1 | grep -iE "error|exception|critical" | tail -5) || true
  if [ -z "$out" ]; then
    printf '%s\n' "(none)"
  else
    printf '%s\n' "$out"
  fi
}

{
  printf '%s\n' "===== $TS ====="

  printf '%s\n' "--- backend errors (last 1h) ---"
  _grep_errors math-correction-backend-1

  printf '%s\n' "--- worker errors (last 1h) ---"
  _grep_errors math-correction-worker-1

  printf '%s\n' "--- DB metrics ---"
  docker compose -f /opt/math-correction/docker-compose.labomaths.yml exec -T postgres sh -lc \
    'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c "
      SELECT
        (SELECT COUNT(*) FROM exams) AS exams,
        (SELECT COUNT(*) FROM student_copies) AS copies,
        (SELECT COUNT(*) FROM corrections) AS corrections,
        (SELECT COUNT(*) FROM corrections WHERE needs_human_review = true) AS needs_review,
        (SELECT COUNT(*) FROM knowledge_documents) AS rag_docs,
        (SELECT COUNT(*) FROM knowledge_chunks) AS rag_chunks
    ;"' 2>&1 || printf '%s\n' "DB QUERY FAILED"

  printf '%s\n' "--- Health ---"
  if health_json=$(curl -fsS http://localhost:8010/health/ready 2>/tmp/wc-health-err); then
    printf '%s\n' "$health_json" | python3 -m json.tool 2>/dev/null || printf '%s\n' "$health_json"
  else
    printf 'HEALTH CHECK FAILED (curl exit %d): %s\n' "$?" "$(cat /tmp/wc-health-err 2>/dev/null)"
  fi

  printf '%s\n' "--- Disk ---"
  df -h /opt/math-correction/storage /var/lib/docker 2>&1 || true

  printf '%s\n' "--- Container stats (top 5 by memory) ---"
  docker stats --no-stream --format "{{.Container}}\t{{.MemUsage}}\t{{.CPUPerc}}" 2>&1 | sort -k2 -h -r | head -5 || true

  printf '\n'
} >> "$LOG" 2>&1
