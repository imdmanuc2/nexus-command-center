#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$ROOT"

test -f backend/data/private/cmdb.env
test -f backend/db/repositories/worker_repository.py
test -f backend/services/generic_stratum_sync_service.py
test -f backend/services/fleet_service.py
test -f backend/jobs/platform_sync_job.py

echo "Package 022 doctor passed."
