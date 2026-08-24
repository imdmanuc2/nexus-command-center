#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

BACKUP_DIR="packages/SBP-076.4-Blockchain-Manager-UI-Integration/backups"

test -f "$BACKUP_DIR/blockchain.html"
test -f "$BACKUP_DIR/blockchain.js"
test -f "$BACKUP_DIR/blockchain.css"

cp "$BACKUP_DIR/blockchain.html" frontend/blockchain.html
cp "$BACKUP_DIR/blockchain.js" frontend/js/blockchain.js
cp "$BACKUP_DIR/blockchain.css" frontend/css/blockchain.css

echo "PASS: SBP-076.4 rollback"
