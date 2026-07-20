#!/usr/bin/env bash
set -euo pipefail
PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_DIR/../.." && pwd)"
TARGET="$REPO_ROOT/backend/db/repositories/worker_repository.py"
PATCH="$PACKAGE_DIR/patch/backend/db/repositories/worker_repository.py"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="${TARGET}.before-package-0341-${STAMP}"
cp "$TARGET" "$BACKUP"
cp "$PATCH" "$TARGET"
python3 -m py_compile "$TARGET"
printf '%s\n' "$BACKUP" > "$PACKAGE_DIR/.last-backup"
echo "Installed worker/pool activity reconciliation fix."
echo "Backup: $BACKUP"
