#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$ROOT"

test -f backend/data/private/cmdb.env
test -f backend/api/server.py
test -f backend/jobs/platform_sync_job.py

for endpoint in \
  api/platform/fleet \
  api/platform/topology \
  api/platform/alerts/summary \
  api/platform/recommendations/summary \
  api/platform/automation/summary \
  api/platform/timeline/latest
do
  curl --max-time 10 -fsS \
    "http://127.0.0.1:8080/$endpoint" \
    >/dev/null
done

echo "Package 024 doctor passed."
