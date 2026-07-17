#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$ROOT/backend/data/private/package-backups/021-platform-stabilization-$STAMP"
cd "$ROOT"
mkdir -p "$BACKUP"
printf '%s\n' "$BACKUP" > "$PKG/.last_backup_dir"
cp backend/db/repositories/alert_repository.py "$BACKUP/alert_repository.py"
cp backend/db/repositories/platform_event_repository.py "$BACKUP/platform_event_repository.py"
cp backend/db/repositories/context_repository.py "$BACKUP/context_repository.py"
python3 "$PKG/scripts/patch_alert_repository.py"
python3 "$PKG/scripts/patch_json_serialization.py"
python3 -m py_compile \
  backend/db/repositories/alert_repository.py \
  backend/db/repositories/platform_event_repository.py \
  backend/db/repositories/context_repository.py \
  backend/services/alert_engine_service.py \
  backend/services/platform_event_service.py \
  backend/services/platform_context_service.py \
  backend/jobs/platform_sync_job.py
sudo systemctl restart nexus-api.service
sleep 2
echo "Package 021 installed."
echo "Backup: $BACKUP"
