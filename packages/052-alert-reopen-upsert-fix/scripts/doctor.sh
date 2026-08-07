#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
for f in \
  "$ROOT/backend/db/repositories/alert_repository.py" \
  "$ROOT/backend/services/alert_engine_service.py" \
  "$ROOT/backend/jobs/platform_sync_job.py"; do
  [[ -f "$f" ]] && echo "PASS: ${f#$ROOT/}" || { echo "FAIL: ${f#$ROOT/}"; exit 1; }
done
python3 -m py_compile "$ROOT/backend/db/repositories/alert_repository.py"
echo "Doctor PASS"
