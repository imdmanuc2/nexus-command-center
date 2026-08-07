#!/usr/bin/env bash
set -euo pipefail
REPO="${NEXUS_REPO:-$HOME/Projects/Seymour/nexus-command-center}"
LATEST="$REPO/backups/package-058-latest"
test -f "$LATEST" || { echo "FAIL: no Package 058 backup pointer"; exit 1; }
BACKUP="$(cat "$LATEST")"
test -d "$BACKUP" || { echo "FAIL: backup missing: $BACKUP"; exit 1; }
cd "$BACKUP"
find . -type f | while read -r rel; do
  rel="${rel#./}"
  mkdir -p "$REPO/$(dirname "$rel")"
  cp -a "$BACKUP/$rel" "$REPO/$rel"
done
sudo systemctl restart nexus-api.service
echo "Rollback PASS: $BACKUP"
