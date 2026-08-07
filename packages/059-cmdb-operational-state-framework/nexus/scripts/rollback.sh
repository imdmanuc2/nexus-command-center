#!/usr/bin/env bash
set -euo pipefail
REPO="${NEXUS_REPO:-$HOME/Projects/Seymour/nexus-command-center}"
LATEST="$REPO/backups/package-059-latest"
test -f "$LATEST" || { echo "No Package 059 backup pointer found."; exit 1; }
BACKUP="$(cat "$LATEST")"
test -d "$BACKUP" || { echo "Backup missing: $BACKUP"; exit 1; }
cd "$REPO"
while IFS= read -r -d '' f; do
  rel="${f#$BACKUP/}"
  mkdir -p "$(dirname "$rel")"
  cp -a "$f" "$rel"
done < <(find "$BACKUP" -type f -print0)
sudo systemctl restart nexus-api.service
echo "Rollback PASS: $BACKUP"
