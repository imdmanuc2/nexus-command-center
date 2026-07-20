#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$PKG/../.." && pwd)"; cd "$ROOT"
[ -f "$PKG/.last-backup" ] || { echo "No package backup recorded"; exit 1; }
BACKUP="$(cat "$PKG/.last-backup")"; [ -d "$BACKUP" ] || { echo "Backup missing: $BACKUP"; exit 1; }
cp -a "$BACKUP/backend/." backend/
if command -v systemctl >/dev/null && systemctl list-unit-files nexus-api.service >/dev/null 2>&1; then sudo systemctl restart nexus-api.service; fi
echo "Application files rolled back. Database tables were preserved."
