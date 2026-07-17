#!/usr/bin/env bash
set -Eeuo pipefail
cd "${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
sudo systemctl restart nexus-api.service
sleep 2
python3 -m backend.jobs.telemetry_collection_job
for e in metrics metrics/current metrics/history metrics/rollups; do
  echo "== $e =="; curl -fsS "http://127.0.0.1:8080/api/platform/$e"|jq '{status,source,count,currentMetricCount,sampleCount,rollups}'
done
systemctl list-timers nexus-telemetry.timer --no-pager
echo "Telemetry storage and rollups verified."
