#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.."&&pwd)"
cd "$PROJECT_ROOT"
mkdir -p backend/db/migrations backend/db/repositories backend/services backend/modules backend/jobs deploy/systemd
cp backend/api/server.py "backend/api/server.py.before-telemetry-$(date +%Y%m%d-%H%M%S)"
for f in \
backend/db/migrations/005_telemetry_storage_rollups.sql \
backend/db/repositories/telemetry_repository.py \
backend/services/telemetry_collector_service.py \
backend/services/metrics_service.py \
backend/modules/metrics.py \
backend/jobs/telemetry_collection_job.py; do
  install -m 0644 "$PACKAGE_ROOT/$f" "$f"
done
cp "$PACKAGE_ROOT/systemd/"* deploy/systemd/
set -a; source backend/data/private/cmdb.env; set +a
PGPASSWORD="$NEXUS_DB_PASSWORD" psql -v ON_ERROR_STOP=1 \
-h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" \
-f backend/db/migrations/005_telemetry_storage_rollups.sql
python3 "$PACKAGE_ROOT/scripts/patch_server.py"
python3 -m py_compile backend/db/repositories/telemetry_repository.py \
backend/services/telemetry_collector_service.py backend/services/metrics_service.py \
backend/modules/metrics.py backend/jobs/telemetry_collection_job.py backend/api/server.py
U="$(id -un)"; G="$(id -gn)"
sed -e "s|__PROJECT_ROOT__|$PROJECT_ROOT|g" -e "s|__NEXUS_USER__|$U|g" -e "s|__NEXUS_GROUP__|$G|g" \
"$PACKAGE_ROOT/systemd/nexus-telemetry.service" >/tmp/nexus-telemetry.service
sudo install -m 0644 /tmp/nexus-telemetry.service /etc/systemd/system/
sudo install -m 0644 "$PACKAGE_ROOT/systemd/nexus-telemetry.timer" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nexus-telemetry.timer
echo "Package 011 installed."
