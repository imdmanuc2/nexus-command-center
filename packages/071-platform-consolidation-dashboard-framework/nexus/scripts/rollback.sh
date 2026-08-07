#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
LATEST="$(find "$REPO_ROOT/backups" -maxdepth 1 -type d -name 'package-071-*' | sort | tail -1)"
[[ -n "$LATEST" ]] || { echo "FAIL: no Package 071 backup found"; exit 1; }
cd "$REPO_ROOT"
for f in backend/modules/platform.py backend/api/server.py frontend/js/home-v2.js frontend/home-v2.html; do
  [[ -f "$LATEST/$f" ]] && cp "$LATEST/$f" "$f"
done
if [[ -f "$LATEST/backend/services/dashboard_summary_service.py" ]]; then
  cp "$LATEST/backend/services/dashboard_summary_service.py" backend/services/
else
  rm -f backend/services/dashboard_summary_service.py
fi
sudo systemctl restart nexus-api.service
sleep 5
echo "Rollback PASS: $LATEST"
