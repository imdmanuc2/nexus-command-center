#!/usr/bin/env bash
set -Eeuo pipefail
BASE=http://127.0.0.1:8080
for ep in fleet workers pools workloads relationships topology; do echo "== $ep =="; curl -fsS "$BASE/api/platform/$ep" | jq '{status,source,count,counts,fleetHealth,fleetHashrate,byType,byStatus}'; echo; done
