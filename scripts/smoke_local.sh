#!/usr/bin/env bash
set -euo pipefail

BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://127.0.0.1:3000}"

check_status() {
  local url="$1"
  local expected="${2:-200}"
  local status
  status="$(curl -sS -o /dev/null -w '%{http_code}' "$url")"
  if [[ "$status" != "$expected" ]]; then
    echo "FAIL $url -> HTTP $status (expected $expected)" >&2
    exit 1
  fi
  echo "OK   $url -> HTTP $status"
}

check_status "$BACKEND_URL/api/system/health"
check_status "$BACKEND_URL/api/scrape/jobs"
check_status "$BACKEND_URL/api/setup/cv-analysis/history"
check_status "$FRONTEND_URL/"
check_status "$FRONTEND_URL/jobs"
check_status "$FRONTEND_URL/cv-analysis"
check_status "$FRONTEND_URL/analytics"

echo "Local smoke checks passed."
