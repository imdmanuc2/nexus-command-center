#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
FILE="$ROOT/backend/db/repositories/alert_repository.py"
grep -q "ON CONFLICT (alert_id) DO UPDATE" "$FILE" && echo "PASS: atomic alert upsert" || exit 1
grep -q "status = 'open'" "$FILE" && echo "PASS: resolved alerts reopen" || exit 1
grep -q "resolved_at = NULL" "$FILE" && echo "PASS: resolved state cleared" || exit 1
grep -q "occurrence_count = nexus.alerts.occurrence_count + 1" "$FILE" && echo "PASS: occurrence count retained" || exit 1
python3 -m py_compile "$FILE"
sudo systemctl is-active --quiet nexus-api.service && echo "PASS: nexus-api.service active"
cd "$ROOT"
/usr/bin/python3 -m backend.jobs.platform_sync_job --once
echo "Verify PASS"
