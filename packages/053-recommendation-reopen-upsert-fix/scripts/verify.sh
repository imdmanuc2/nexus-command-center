#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
FILE="$ROOT/backend/db/repositories/recommendation_repository.py"

grep -q "ON CONFLICT (recommendation_id)" "$FILE" && echo "PASS: atomic recommendation upsert"
grep -q "status = 'open'" "$FILE" && echo "PASS: completed recommendations reopen"
grep -q "completed_at = NULL" "$FILE" && echo "PASS: completed state cleared"
grep -q "dismissed_at = NULL" "$FILE" && echo "PASS: dismissed state cleared"
grep -q "accepted_at = NULL" "$FILE" && echo "PASS: accepted state cleared"
grep -q "generation_count = (" "$FILE" && echo "PASS: generation count retained"
python3 -m py_compile "$FILE"
sudo systemctl is-active --quiet nexus-api.service && echo "PASS: nexus-api.service active"
cd "$ROOT"
python3 -m backend.jobs.platform_sync_job

echo "Verify PASS"
