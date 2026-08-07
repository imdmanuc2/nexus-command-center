#!/usr/bin/env bash
set -euo pipefail
PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "$PACKAGE_DIR/../.." && pwd)"
cd "$ROOT"
STAMP="$(date +%Y%m%d-%H%M%S)"
cp backend/services/generic_stratum_sync_service.py \
  "backend/services/generic_stratum_sync_service.py.before-package-051-$STAMP"
cp "$PACKAGE_DIR/payload/backend/services/generic_stratum_sync_service.py" \
  backend/services/generic_stratum_sync_service.py
python3 -m py_compile backend/services/generic_stratum_sync_service.py
sudo systemctl restart nexus-api.service
sudo systemctl is-active --quiet nexus-api.service
echo "Install PASS"
