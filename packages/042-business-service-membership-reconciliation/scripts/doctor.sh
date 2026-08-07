#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$PKG/../.." && pwd)"
for c in python3 psql curl; do command -v "$c" >/dev/null || { echo "$c missing"; exit 1; }; done
[[ -f "$ROOT/backend/data/private/cmdb.env" ]] || { echo "cmdb.env missing"; exit 1; }
[[ -f "$ROOT/backend/db/migrations/029_service_topology_business_services.sql" ]] || { echo "Package 040 migration missing"; exit 1; }
[[ -f "$ROOT/backend/services/service_operations_service.py" ]] || { echo "Package 041 service missing"; exit 1; }
echo "Package 042 doctor PASS"
