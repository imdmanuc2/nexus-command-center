#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

test -f "$PKG/.last_backup_dir" || {
  echo "No Package 027 backup state found."
  exit 1
}

BACKUP="$(cat "$PKG/.last_backup_dir")"
cd "$ROOT"

cp "$BACKUP/backend/services/automation_engine_service.py" \
  backend/services/automation_engine_service.py
rm -rf backend/executors

sudo systemctl restart nexus-api.service

echo "Package 027 application rollback complete."
echo "Migration 018 catalog records were retained intentionally."
