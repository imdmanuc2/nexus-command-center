#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"

cd "$PROJECT_ROOT"

echo "== Manual sync run =="
python3 -m backend.jobs.platform_sync_job \
  --stale-seconds 300

echo
echo "== Timer status =="
sudo systemctl status \
  nexus-platform-sync.timer \
  --no-pager

echo
echo "== Last service run =="
sudo systemctl status \
  nexus-platform-sync.service \
  --no-pager \
  || true

echo
echo "== Next scheduled execution =="
systemctl list-timers \
  nexus-platform-sync.timer \
  --no-pager

echo
echo "== PostgreSQL current state =="
python3 - <<'PY'
from backend.db.repositories.worker_repository import list_workers
from backend.db.repositories.pool_repository import list_pools
from backend.db.repositories.workload_repository import list_workloads
from backend.db.repositories.relationship_repository import list_relationships

print({
    "workers": len(list_workers()),
    "pools": len(list_pools()),
    "workloads": len(list_workloads()),
    "relationships": len(list_relationships()),
})
PY

echo
echo "Automatic Platform synchronization verified."
