#!/usr/bin/env bash
set -euo pipefail
ROOT="$HOME/Projects/Seymour/nexus-command-center"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$ROOT/backups/package-060-$STAMP"
mkdir -p "$BACKUP"
cd "$ROOT"
for f in \
  backend/db/repositories/worker_repository.py \
  backend/jobs/platform_sync_job.py \
  backend/services/topology_service.py \
  frontend/js/graph.js; do
  mkdir -p "$BACKUP/$(dirname "$f")"
  cp "$f" "$BACKUP/$f"
done
cp -a "$PKG/payload/." "$ROOT/"
python3 -m py_compile \
  backend/db/repositories/worker_repository.py \
  backend/services/operational_state_engine.py \
  backend/jobs/platform_sync_job.py
sudo systemctl restart nexus-api.service
sleep 2
systemctl is-active --quiet nexus-api.service
echo "Backup: $BACKUP"
echo 'Install PASS'
