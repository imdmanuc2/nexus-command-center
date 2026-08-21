#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

LATEST="$(
  find backups -maxdepth 1 -type d \
    -name 'pkg080-*' \
    -printf '%T@ %p\n' 2>/dev/null \
  | sort -nr \
  | head -1 \
  | cut -d' ' -f2-
)"

if [[ -z "${LATEST:-}" || ! -d "$LATEST" ]]; then
    echo "ERROR: Package 080 backup not found"
    exit 1
fi

cp "$LATEST/server.py" backend/api/server.py
cp "$LATEST/blockchain_management.py" \
   backend/modules/blockchain_management.py
cp "$LATEST/nav.js" frontend/js/nav.js

rm -f \
  backend/services/blockchain_operations_service.py \
  frontend/blockchain.html \
  frontend/js/blockchain.js \
  frontend/css/blockchain.css

python3 -m py_compile backend/api/server.py

echo "PASS: Package 080 rolled back"
echo "Restart nexus-api.service to activate rollback."
