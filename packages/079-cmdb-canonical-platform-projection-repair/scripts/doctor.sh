#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
TARGET="$ROOT/backend/services/platform_inventory_service.py"

echo "===== PACKAGE 079 DOCTOR ====="

test -f "$TARGET"
echo "PASS: platform inventory service exists"

grep -q 'def inventory' "$TARGET"
echo "PASS: inventory function exists"

grep -q 'from backend.db.repositories.pool_repository import list_pools' "$TARGET"
echo "PASS: pool repository dependency exists"

grep -q 'from backend.db.repositories.worker_repository import list_workers' "$TARGET"
echo "PASS: worker repository dependency exists"

python3 -m py_compile "$TARGET"
echo "PASS: current platform inventory service compiles"

echo "PACKAGE 079 DOCTOR PASS"
