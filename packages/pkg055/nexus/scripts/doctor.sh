#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO="$HOME/Projects/Seymour/nexus-command-center"
test -d "$REPO"
test -f "$PACKAGE_DIR/payload/backend/services/generic_stratum_sync_service.py"
test -f "$PACKAGE_DIR/payload/backend/data/config/generic_stratum_pools.json"
curl -fsS http://192.168.1.169:3000/api/ckpool/status >/dev/null
echo "PASS: repository and payload"
echo "PASS: CKPool telemetry reachable"
echo "Doctor PASS"
