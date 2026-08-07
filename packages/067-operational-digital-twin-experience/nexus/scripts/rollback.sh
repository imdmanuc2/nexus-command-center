#!/usr/bin/env bash
set -euo pipefail
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_ROOT/../../.." && pwd)"
BACKUP="${1:-$(find "$REPO_ROOT/backups" -maxdepth 1 -type d -name 'package-067-*' | sort | tail -1)}"
[[ -n "$BACKUP" && -d "$BACKUP" ]] || { echo "No Package 067 backup found"; exit 1; }
for f in frontend/cmdb-object.html frontend/js/cmdb-object.js frontend/css/cmdb-object.css backend/services/cmdb_object_service.py; do
  [[ -f "$BACKUP/$f" ]] && cp "$BACKUP/$f" "$REPO_ROOT/$f"
done
sudo systemctl restart nexus-api.service || true
echo "Rollback PASS: $BACKUP"
