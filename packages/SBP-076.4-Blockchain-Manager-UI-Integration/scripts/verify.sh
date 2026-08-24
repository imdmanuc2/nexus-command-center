#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

HTML="frontend/blockchain.html"
JS="frontend/js/blockchain.js"
CSS="frontend/css/blockchain.css"
PKG="packages/SBP-076.4-Blockchain-Manager-UI-Integration"

echo "===== SBP-076.4 VERIFY ====="

grep -q 'nexus-page-shell blockchain-page' "$HTML"
echo "PASS: shared Nexus page shell"

grep -q '>Blockchain Runtimes<' "$HTML"
echo "PASS: blockchain runtime terminology"

if grep -q 'data-filter="BTC"' "$HTML" \
  || grep -q 'data-filter="BCH"' "$HTML" \
  || grep -q 'data-filter="XMR"' "$HTML"; then
    echo "FAIL: hard-coded provider filters remain"
    exit 1
fi

echo "PASS: provider filters are provider-neutral"

grep -q 'function renderCatalogFilters()' "$JS"
grep -q 'renderCatalogFilters();' "$JS"
echo "PASS: dynamic catalog filters"

grep -q '\["running", "online"\]' "$JS"
echo "PASS: online nodes count as operational"

grep -q 'Independent / discovered' "$JS"
grep -q 'Seymour managed' "$JS"
echo "PASS: ownership distinction"

grep -q 'syncProgress' "$JS"
grep -q 'blockchain-progress-bar' "$JS"
echo "PASS: sync progress preserved"

grep -q '/api/blockchain/operations' "$JS"
grep -q '/api/blockchain/catalog' "$JS"
echo "PASS: canonical API routes preserved"

grep -q 'SBP-076.4 — shared Nexus page framing' "$CSS"
echo "PASS: Blockchain page frame"

if find "$PKG" -type d -name __pycache__ -o -type f -name '*.pyc' | grep -q .; then
    echo "FAIL: generated artifacts found"
    exit 1
fi

echo "PASS: package bytecode-free"
echo
echo "SBP-076.4 VERIFY PASS"
