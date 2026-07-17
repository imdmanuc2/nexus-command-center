#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$PROJECT_ROOT/backend/data/private/package-backups/010-automatic-sync-stale-reconciliation-$STAMP"
SERVICE_FILE="/etc/systemd/system/nexus-platform-sync.service"
TIMER_FILE="/etc/systemd/system/nexus-platform-sync.timer"

cd "$PROJECT_ROOT"

mkdir -p "$BACKUP_DIR" backend/jobs
printf '%s\n' "$BACKUP_DIR" > "$PACKAGE_ROOT/.last_backup_dir"

for file in backend/jobs/__init__.py backend/jobs/platform_sync_job.py; do
  if [[ -f "$file" ]]; then
    cp "$file" "$BACKUP_DIR/$(basename "$file")"
  fi
done

if sudo test -f "$SERVICE_FILE"; then
  sudo cp "$SERVICE_FILE" "$BACKUP_DIR/nexus-platform-sync.service"
fi

if sudo test -f "$TIMER_FILE"; then
  sudo cp "$TIMER_FILE" "$BACKUP_DIR/nexus-platform-sync.timer"
fi

install -m 0644 \
  "$PACKAGE_ROOT/backend/jobs/__init__.py" \
  backend/jobs/__init__.py

install -m 0644 \
  "$PACKAGE_ROOT/backend/jobs/platform_sync_job.py" \
  backend/jobs/platform_sync_job.py

NEXUS_USER="$(id -un)"
NEXUS_GROUP="$(id -gn)"

sed \
  -e "s|__PROJECT_ROOT__|$PROJECT_ROOT|g" \
  -e "s|__NEXUS_USER__|$NEXUS_USER|g" \
  -e "s|__NEXUS_GROUP__|$NEXUS_GROUP|g" \
  "$PACKAGE_ROOT/systemd/nexus-platform-sync.service" \
  > /tmp/nexus-platform-sync.service

sudo install -m 0644 \
  /tmp/nexus-platform-sync.service \
  "$SERVICE_FILE"

sudo install -m 0644 \
  "$PACKAGE_ROOT/systemd/nexus-platform-sync.timer" \
  "$TIMER_FILE"

python3 -m py_compile \
  backend/jobs/platform_sync_job.py \
  scripts/sync_platform_inventory.py

sudo systemctl daemon-reload
sudo systemctl enable --now nexus-platform-sync.timer

echo
echo "Package 010 installed."
echo "Backup: $BACKUP_DIR"
echo
sudo systemctl status nexus-platform-sync.timer --no-pager
