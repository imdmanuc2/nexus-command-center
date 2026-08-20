#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
TARGET="$ROOT/backend/services/platform_inventory_service.py"

LATEST="$(
  find "$ROOT/backups" -maxdepth 1 -type f \
    -name 'platform_inventory_service.py.before-079-*' \
    -printf '%T@ %p\n' 2>/dev/null \
  | sort -nr \
  | head -1 \
  | cut -d' ' -f2-
)"

if [[ -z "${LATEST:-}" || ! -f "$LATEST" ]]; then
  echo "ERROR: Package 079 backup not found."
  exit 1
fi

cp "$LATEST" "$TARGET"
python3 -m py_compile "$TARGET"

echo "Restored: $LATEST"
echo "Restart nexus-api.service to activate rollback."
