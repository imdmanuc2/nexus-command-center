#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
cd "$REPO_ROOT"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$REPO_ROOT/backups/package-071-$STAMP"
mkdir -p "$BACKUP/backend/services" "$BACKUP/backend/modules" "$BACKUP/backend/api" "$BACKUP/frontend/js" "$BACKUP/frontend"
for f in backend/modules/platform.py backend/api/server.py frontend/js/home-v2.js frontend/home-v2.html; do
  mkdir -p "$BACKUP/$(dirname "$f")"
  cp "$f" "$BACKUP/$f"
done
[[ -f backend/services/dashboard_summary_service.py ]] && cp backend/services/dashboard_summary_service.py "$BACKUP/backend/services/" || true
cp "$PACKAGE_ROOT/payload/backend/services/dashboard_summary_service.py" backend/services/
cp "$PACKAGE_ROOT/payload/backend/modules/platform.py" backend/modules/platform.py
cp "$PACKAGE_ROOT/payload/backend/api/server.py" backend/api/server.py
cp "$PACKAGE_ROOT/payload/frontend/js/home-v2.js" frontend/js/home-v2.js
cp "$PACKAGE_ROOT/payload/frontend/home-v2.html" frontend/home-v2.html
sudo systemctl restart nexus-api.service
sleep 5
echo "Backup: $BACKUP"
echo "Install PASS"
