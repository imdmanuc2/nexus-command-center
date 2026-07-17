#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$ROOT"
test -f backend/db/repositories/alert_repository.py
test -f backend/db/repositories/platform_event_repository.py
test -f backend/db/repositories/context_repository.py
test -f backend/jobs/platform_sync_job.py
test -f backend/data/private/cmdb.env
echo "Package 021 doctor passed."
