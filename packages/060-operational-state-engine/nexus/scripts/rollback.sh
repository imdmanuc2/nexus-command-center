#!/usr/bin/env bash
set -euo pipefail
ROOT="$HOME/Projects/Seymour/nexus-command-center"
BACKUP="${1:-$(find "$ROOT/backups" -maxdepth 1 -type d -name 'package-060-*' | sort | tail -1)}"
test -n "$BACKUP" -a -d "$BACKUP"
cd "$ROOT"
cp -a "$BACKUP/." "$ROOT/"
rm -f backend/services/operational_state_engine.py
sudo systemctl restart nexus-api.service
echo "Rollback PASS: $BACKUP"
