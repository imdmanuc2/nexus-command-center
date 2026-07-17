#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE="$PACKAGE_ROOT/.last_backup_dir"
test -f "$STATE" || { echo "No backup state found."; exit 1; }
BACKUP_DIR="$(cat "$STATE")"
cd "$PROJECT_ROOT"
cp "$BACKUP_DIR/server.py" backend/api/server.py
for file in fleet_service.py worker_service.py pool_service.py workload_service.py relationship_service.py topology_service.py; do
  if [[ -f "$BACKUP_DIR/$file" ]]; then
    cp "$BACKUP_DIR/$file" "backend/services/$file"
  else
    rm -f "backend/services/$file"
  fi
done
if [[ -f "$BACKUP_DIR/platform.py" ]]; then
  cp "$BACKUP_DIR/platform.py" backend/modules/platform.py
else
  rm -f backend/modules/platform.py
fi
python3 -m py_compile backend/api/server.py
echo "Rollback complete."
