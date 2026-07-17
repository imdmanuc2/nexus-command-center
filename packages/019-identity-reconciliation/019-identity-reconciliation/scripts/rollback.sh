#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}";PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)";test -f "$PKG/.last_backup_dir" || { echo 'No backup state.';exit 1; };BACKUP="$(cat "$PKG/.last_backup_dir")";cp "$BACKUP/worker_repository.py" "$ROOT/backend/db/repositories/worker_repository.py";echo 'Package 019 rollback complete.'
