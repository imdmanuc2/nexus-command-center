#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$ROOT"

test -f scripts/sync_platform_inventory.py
test -f backend/db/repositories/worker_repository.py
test -f backend/db/repositories/workload_repository.py

grep -q \
  'canonical_worker_id = saved_worker\["workerId"\]' \
  scripts/sync_platform_inventory.py \
  && {
    echo "Package 020 already appears installed."
    exit 0
  }

grep -q \
  'upsert_worker(worker)' \
  scripts/sync_platform_inventory.py

echo "Package 020 doctor passed."
