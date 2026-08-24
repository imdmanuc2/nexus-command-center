#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

PKG="packages/SBP-076.5-Canonical-Blockchain-Runtime-Health-Model"
BACKUP="$PKG/backups/blockchain_operations_service.py"

test -f "$BACKUP"

cp "$BACKUP" \
  backend/services/blockchain_operations_service.py

rm -f \
  backend/services/blockchain_runtime_health_service.py

echo "SBP-076.5 ROLLBACK PASS"
