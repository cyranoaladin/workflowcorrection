#!/usr/bin/env bash
set -euo pipefail

base="${1:-http://localhost:8000}"

echo "[smoke-test] Health: $base/health"
curl -fsS "$base/health" | sed 's/.*/[smoke-test] &/'

echo "[smoke-test] Create exam..."
exam_json="$(curl -fsS -X POST "$base/exams" -H 'Content-Type: application/json' -d '{"title":"Demo Exam","level":"test","session":"2026"}')"
echo "$exam_json"

echo "[smoke-test] List exams..."
curl -fsS "$base/exams" | head -c 500; echo

echo "[smoke-test] OK (upload/process steps require PDF files)."

