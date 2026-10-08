#!/usr/bin/env bash
set -euo pipefail

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$DIR"

echo "=========================================================="
echo "🧪 RUNNING ALL TESTS (BACKEND & FRONTEND)"
echo "=========================================================="

# 1. Frontend tests
echo ""
echo "[1/2] Running Frontend Tests & Lint..."
npm --prefix frontend run test
npm --prefix frontend run lint

# 2. Backend tests in isolated clean temporary workspace
echo ""
echo "[2/2] Running Backend Pytest Suite..."
TMP_TEST_DIR=$(mktemp -d -t career-test-XXXXXX)
trap 'rm -rf "$TMP_TEST_DIR"' EXIT

PYTHONPATH=. \
ENVIRONMENT=test \
MULTI_TENANT_ENABLED=false \
DATA_PATH="$TMP_TEST_DIR" \
DATABASE_URL="sqlite:///$TMP_TEST_DIR/test.db" \
./backend/.venv/bin/pytest backend/tests -q

echo ""
echo "=========================================================="
echo "✅ ALL BACKEND & FRONTEND TESTS PASSED SUCCESSFULLY!"
echo "=========================================================="
