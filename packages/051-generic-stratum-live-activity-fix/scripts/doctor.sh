#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
for f in \
  backend/services/generic_stratum_sync_service.py \
  backend/db/repositories/worker_repository.py \
  backend/services/worker_activity_reconciliation_service.py \
  backend/services/topology_reconciliation_service.py
do
  test -f "$f" || { echo "FAIL: missing $f"; exit 1; }
  echo "PASS: $f"
done
python3 -m py_compile backend/services/generic_stratum_sync_service.py
echo "Doctor PASS"
