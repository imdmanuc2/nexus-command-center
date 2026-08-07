#!/usr/bin/env bash
set -euo pipefail
REPO="$HOME/Projects/Seymour/nexus-command-center"
BACKUP="${1:-$(find "$REPO/backups" -maxdepth 1 -type d -name 'package-0582-*' | sort | tail -n 1)}"
test -n "$BACKUP"
test -f "$BACKUP/backend/db/repositories/worker_repository.py"
cp "$BACKUP/backend/db/repositories/worker_repository.py" "$REPO/backend/db/repositories/worker_repository.py"
sudo systemctl restart nexus-api.service
echo "Rollback PASS: $BACKUP"
