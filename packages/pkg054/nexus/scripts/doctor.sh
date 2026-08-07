#!/usr/bin/env bash
set -euo pipefail
cd ~/Projects/Seymour/nexus-command-center
[[ -f backend/services/generic_stratum_sync_service.py ]] && echo 'PASS: generic Stratum service' || exit 1
[[ -f backend/data/config/generic_stratum_pools.json ]] && echo 'PASS: generic Stratum config' || exit 1
curl -fsS http://192.168.1.169:3000/api/ckpool/status >/dev/null && echo 'PASS: CKPool telemetry reachable' || { echo 'FAIL: CKPool telemetry unreachable'; exit 1; }
echo 'Doctor PASS'
