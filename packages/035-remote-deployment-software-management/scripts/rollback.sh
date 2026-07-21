#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$PKG/../.." && pwd)"; [ -f "$PKG/.last-backup" ] || { echo "No backup recorded"; exit 1; }
BACKUP="$(cat "$PKG/.last-backup")"; cd "$ROOT"; cp -a "$BACKUP/." .
if command -v systemctl >/dev/null; then sudo systemctl restart nexus-api.service || true; fi
echo "Package 035 files rolled back. Database tables were retained for audit safety."
