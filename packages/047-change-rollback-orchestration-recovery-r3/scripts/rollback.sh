#!/usr/bin/env bash
set -euo pipefail

PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "$PKG_DIR/../.." && pwd)"

LATEST="$(
  find "$ROOT/packages/backups"     -maxdepth 1     -type d     -name '047-change-rollback-r3-*'     | sort     | tail -n 1
)"

if [ -z "$LATEST" ] || [ ! -f "$LATEST/backend/api/server.py" ]; then
  echo "No Package 047 Revision 3 server.py backup found." >&2
  exit 1
fi

sudo systemctl stop nexus-change-rollback-worker.service 2>/dev/null || true
cp "$LATEST/backend/api/server.py" "$ROOT/backend/api/server.py"
python3 -m py_compile "$ROOT/backend/api/server.py"
sudo systemctl restart nexus-api.service

echo "Package 047 Revision 3 API routing rollback complete."
echo "Restored: $LATEST/backend/api/server.py"
