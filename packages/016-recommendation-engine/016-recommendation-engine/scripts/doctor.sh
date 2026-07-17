#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$PROJECT_ROOT"

test -f backend/data/private/cmdb.env
test -f backend/jobs/platform_sync_job.py

curl -fsS http://127.0.0.1:8080/api/platform/context \
  | jq -e '.status == "ok"' >/dev/null

curl -fsS http://127.0.0.1:8080/api/platform/alerts \
  | jq -e '.status == "ok"' >/dev/null

echo "Package 016 doctor passed."
