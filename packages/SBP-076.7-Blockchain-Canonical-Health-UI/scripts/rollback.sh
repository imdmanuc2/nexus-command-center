#!/usr/bin/env bash
set -euo pipefail

ROOT="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/../../.." &&
  pwd
)"

BACKUP="$(
  find "$ROOT/backups" \
    -maxdepth 1 \
    -type d \
    -name 'sbp-076.7-*' \
    | sort \
    | tail -1
)"

test -n "$BACKUP"
test -f "$BACKUP/frontend/blockchain.html"
test -f "$BACKUP/frontend/js/blockchain.js"
test -f "$BACKUP/frontend/css/blockchain.css"

cp "$BACKUP/frontend/blockchain.html" \
  "$ROOT/frontend/blockchain.html"

cp "$BACKUP/frontend/js/blockchain.js" \
  "$ROOT/frontend/js/blockchain.js"

cp "$BACKUP/frontend/css/blockchain.css" \
  "$ROOT/frontend/css/blockchain.css"

echo "PASS: SBP-076.7 rollback restored $BACKUP"
