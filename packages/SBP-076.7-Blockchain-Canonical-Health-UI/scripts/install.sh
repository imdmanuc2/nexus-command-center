#!/usr/bin/env bash
set -euo pipefail

ROOT="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/../../.." &&
  pwd
)"

PKG="$ROOT/packages/SBP-076.7-Blockchain-Canonical-Health-UI"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$ROOT/backups/sbp-076.7-$STAMP"

mkdir -p \
  "$BACKUP/frontend/js" \
  "$BACKUP/frontend/css"

cp "$ROOT/frontend/blockchain.html" \
  "$BACKUP/frontend/blockchain.html"

cp "$ROOT/frontend/js/blockchain.js" \
  "$BACKUP/frontend/js/blockchain.js"

cp "$ROOT/frontend/css/blockchain.css" \
  "$BACKUP/frontend/css/blockchain.css"

cp "$PKG/payload/frontend/blockchain.html" \
  "$ROOT/frontend/blockchain.html"

cp "$PKG/payload/frontend/js/blockchain.js" \
  "$ROOT/frontend/js/blockchain.js"

cp "$PKG/payload/frontend/css/blockchain.css" \
  "$ROOT/frontend/css/blockchain.css"

echo "backup=$BACKUP"
echo "PASS: SBP-076.7 installed"
