#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
BACKUP=$(ls -dt "$ROOT"/backups/package-061-* 2>/dev/null | head -n1 || true)
[[ -n "$BACKUP" ]] || { echo "No Package 061 backup found"; exit 1; }
cp -a "$BACKUP/." "$ROOT/"
sudo systemctl restart nexus-api.service
echo "Rollback PASS: $BACKUP"
