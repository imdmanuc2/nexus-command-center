#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$ROOT"
test -f backend/data/private/cmdb.env
test -f backend/jobs/platform_sync_job.py
curl -fsS http://127.0.0.1:8080/api/platform/automation/summary \
  | jq -e '.status=="ok"' >/dev/null
echo "Package 018 doctor passed."
