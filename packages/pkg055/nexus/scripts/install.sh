#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO="$HOME/Projects/Seymour/nexus-command-center"
STAMP="$(date +%Y%m%d-%H%M%S)"
cd "$REPO"
cp backend/services/generic_stratum_sync_service.py "backend/services/generic_stratum_sync_service.py.before-pkg055-$STAMP"
cp backend/data/config/generic_stratum_pools.json "backend/data/config/generic_stratum_pools.json.before-pkg055-$STAMP"
cp "$PACKAGE_DIR/payload/backend/services/generic_stratum_sync_service.py" backend/services/generic_stratum_sync_service.py
cp "$PACKAGE_DIR/payload/backend/data/config/generic_stratum_pools.json" backend/data/config/generic_stratum_pools.json
python3 -m py_compile backend/services/generic_stratum_sync_service.py
sudo systemctl restart nexus-api.service
sleep 2
systemctl is-active --quiet nexus-api.service
echo "Install PASS"
