#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_ROOT/../../.." && pwd)"

cd "$REPO_ROOT"
BACKUP="$(find "$REPO_ROOT/backups" -maxdepth 1 -type d -name 'package-065-*' | sort | tail -1)"
test -n "$BACKUP" || { echo "No Package 065 backup found"; exit 1; }
cp -a "$BACKUP/." "$REPO_ROOT/"
sudo systemctl restart nexus-api.service
echo "Rollback PASS: $BACKUP"
