#!/usr/bin/env bash
set -eu
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
LOG=/var/log/wc-golive-monitor.log

{
  echo "===== $TS ====="

  echo "--- backend errors (last 1h) ---"
  docker logs math-correction-backend-1 --since 1h 2>&1 | grep -iE "error|exception|critical" | tail -5 || echo "(none)"

  echo "--- worker errors (last 1h) ---"
  docker logs math-correction-worker-1 --since 1h 2>&1 | grep -iE "error|exception|critical" | tail -5 || echo "(none)"

  echo "--- DB metrics ---"
  docker compose -f /opt/math-correction/docker-compose.labomaths.yml exec -T postgres sh -lc \
    'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c "
      SELECT
        (SELECT COUNT(*) FROM exams) AS exams,
        (SELECT COUNT(*) FROM student_copies) AS copies,
        (SELECT COUNT(*) FROM corrections) AS corrections,
        (SELECT COUNT(*) FROM corrections WHERE needs_human_review = true) AS needs_review,
        (SELECT COUNT(*) FROM knowledge_documents) AS rag_docs,
        (SELECT COUNT(*) FROM knowledge_chunks) AS rag_chunks
    ;"' 2>&1 | head -3

  echo "--- Health ---"
  curl -fsS http://localhost:8010/health/ready 2>&1 | python3 -m json.tool | head -20

  echo "--- Disk ---"
  df -h /opt/math-correction/storage /var/lib/docker 2>&1 | tail -3

  echo "--- Container stats (top 5 by memory) ---"
  docker stats --no-stream --format "{{.Container}}\t{{.MemUsage}}\t{{.CPUPerc}}" | sort -k2 -h -r | head -5

  echo ""
} >> "$LOG" 2>&1
