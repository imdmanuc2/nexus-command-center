#!/usr/bin/env bash
set -euo pipefail
PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ -f "$PACKAGE_DIR/.last-backup" ]] || { echo "No package backup recorded."; exit 1; }
BACKUP="$(cat "$PACKAGE_DIR/.last-backup")"
[[ -f "$BACKUP" ]] || { echo "Backup not found: $BACKUP"; exit 1; }
TARGET="${BACKUP%%.before-package-0341-*}"
cp "$BACKUP" "$TARGET"
python3 -m py_compile "$TARGET"
echo "Rolled back: $TARGET"
