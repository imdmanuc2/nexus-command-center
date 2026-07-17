#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$ROOT"

test -f backend/data/private/cmdb.env
test -f backend/services/topology_service.py
test -f backend/db/repositories/relationship_repository.py
test -f frontend/js/nexus-platform-explorer.js
test -f backend/jobs/platform_sync_job.py

curl -fsS http://127.0.0.1:8080/api/platform/workers \
  | jq -e '.status == "ok" and .invariant.valid == true' >/dev/null

echo "Package 023 doctor passed."
