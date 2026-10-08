#!/usr/bin/env bash
# ==============================================================================
# Otonom İş Bulma Sistemi — Kapsamlı Test Çalıştırıcı
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

echo "========================================================"
echo "🚀 1. Backend Testleri ve Kod Kapsamı (pytest + coverage)"
echo "========================================================"
if [ -d "backend/.venv" ]; then
    ./backend/.venv/bin/python -m pytest backend/tests/ -v --cov=backend/app --cov-report=term-missing
else
    python3 -m pytest backend/tests/ -v --cov=backend/app --cov-report=term-missing
fi

echo ""
echo "========================================================"
echo "🎨 2. Frontend Birim ve Güvenlik Testleri (Node test runner)"
echo "========================================================"
cd "$DIR/frontend"
npm test

echo ""
echo "========================================================"
echo "✅ Tüm testler başarıyla tamamlandı!"
echo "========================================================"
