#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
for f in \
  backend/db/repositories/recommendation_repository.py \
  backend/services/recommendation_engine_service.py \
  backend/jobs/platform_sync_job.py
 do
  test -f "$ROOT/$f" && echo "PASS: $f" || { echo "FAIL: $f"; exit 1; }
done
python3 -m py_compile "$ROOT/backend/db/repositories/recommendation_repository.py"
echo "Doctor PASS"
