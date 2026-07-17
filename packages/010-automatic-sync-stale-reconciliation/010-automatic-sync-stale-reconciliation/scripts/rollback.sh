#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_FILE="$PACKAGE_ROOT/.last_backup_dir"
SERVICE_FILE="/etc/systemd/system/nexus-platform-sync.service"
TIMER_FILE="/etc/systemd/system/nexus-platform-sync.timer"

test -f "$STATE_FILE" || {
  echo "No Package 010 backup state found."
  exit 1
}

BACKUP_DIR="$(cat "$STATE_FILE")"
cd "$PROJECT_ROOT"

sudo systemctl disable --now nexus-platform-sync.timer || true

if [[ -f "$BACKUP_DIR/platform_sync_job.py" ]]; then
  cp "$BACKUP_DIR/platform_sync_job.py" backend/jobs/platform_sync_job.py
else
  rm -f backend/jobs/platform_sync_job.py
fi

if [[ -f "$BACKUP_DIR/__init__.py" ]]; then
  cp "$BACKUP_DIR/__init__.py" backend/jobs/__init__.py
fi

if [[ -f "$BACKUP_DIR/nexus-platform-sync.service" ]]; then
  sudo cp "$BACKUP_DIR/nexus-platform-sync.service" "$SERVICE_FILE"
else
  sudo rm -f "$SERVICE_FILE"
fi

if [[ -f "$BACKUP_DIR/nexus-platform-sync.timer" ]]; then
  sudo cp "$BACKUP_DIR/nexus-platform-sync.timer" "$TIMER_FILE"
else
  sudo rm -f "$TIMER_FILE"
fi

sudo systemctl daemon-reload

echo "Package 010 rollback complete."
