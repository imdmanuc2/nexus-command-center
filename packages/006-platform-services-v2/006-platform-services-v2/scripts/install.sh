#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$PROJECT_ROOT/backend/data/private/package-backups/006-platform-services-$STAMP"

cd "$PROJECT_ROOT"
mkdir -p "$BACKUP_DIR" backend/services backend/modules
printf '%s\n' "$BACKUP_DIR" > "$PACKAGE_ROOT/.last_backup_dir"
cp backend/api/server.py "$BACKUP_DIR/server.py"

for file in fleet_service.py worker_service.py pool_service.py workload_service.py relationship_service.py topology_service.py; do
  [[ -f "backend/services/$file" ]] && cp "backend/services/$file" "$BACKUP_DIR/$file"
  install -m 0644 "$PACKAGE_ROOT/backend/services/$file" "backend/services/$file"
done

[[ -f backend/modules/platform.py ]] && cp backend/modules/platform.py "$BACKUP_DIR/platform.py"
install -m 0644 "$PACKAGE_ROOT/backend/modules/platform.py" backend/modules/platform.py

python3 "$PACKAGE_ROOT/scripts/patch_server.py"

python3 -m py_compile   backend/services/fleet_service.py   backend/services/worker_service.py   backend/services/pool_service.py   backend/services/workload_service.py   backend/services/relationship_service.py   backend/services/topology_service.py   backend/modules/platform.py   backend/api/server.py

echo "Package 006 v2 installed."
echo "Backup: $BACKUP_DIR"
