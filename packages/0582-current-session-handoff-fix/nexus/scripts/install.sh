#!/usr/bin/env bash
set -euo pipefail
REPO="$HOME/Projects/Seymour/nexus-command-center"
PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$REPO/backups/package-0582-$STAMP"
mkdir -p "$BACKUP/backend/db/repositories"
cp "$REPO/backend/db/repositories/worker_repository.py" "$BACKUP/backend/db/repositories/worker_repository.py"
cp "$PKG_DIR/payload/backend/db/repositories/worker_repository.py" "$REPO/backend/db/repositories/worker_repository.py"
python3 -m py_compile "$REPO/backend/db/repositories/worker_repository.py"
sudo systemctl restart nexus-api.service
sleep 2
systemctl is-active --quiet nexus-api.service
echo "Backup: $BACKUP"
echo "Install PASS"
