#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

HTML="frontend/blockchain.html"
JS="frontend/js/blockchain.js"
CSS="frontend/css/blockchain.css"
PKG="packages/SBP-076.4-Blockchain-Manager-UI-Integration"

echo "===== SBP-076.4 DOCTOR ====="

for file in "$HTML" "$JS" "$CSS"; do
    test -f "$file"
    echo "PASS: $file exists"
done

grep -q 'id="blockchainManagedCount"' "$HTML"
grep -q 'id="blockchainCatalogFilters"' "$HTML"
grep -q 'function managedCard(node)' "$JS"
grep -q 'async function loadOperations()' "$JS"
grep -q 'async function loadCatalog()' "$JS"
grep -q '/api/blockchain/catalog' "$JS"

echo "PASS: pre-install Blockchain UI contract"

if find "$PKG" -type d -name __pycache__ -o -type f -name '*.pyc' | grep -q .; then
    echo "FAIL: generated Python artifacts found in package"
    exit 1
fi

echo "PASS: package artifact safety"
echo "SBP-076.4 DOCTOR PASS"
