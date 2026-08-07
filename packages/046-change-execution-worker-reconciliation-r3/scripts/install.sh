#!/usr/bin/env bash
set -euo pipefail
PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "$PKG_DIR/../.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
SERVICE_USER="${SUDO_USER:-$(id -un)}"
sudo systemctl stop nexus-change-execution-worker.service 2>/dev/null || true
BACKUP="$ROOT/packages/backups/046-change-execution-worker-$STAMP"
mkdir -p "$BACKUP"

for f in \
 backend/api/server.py \
 backend/db/repositories/change_execution_repository.py \
 backend/services/change_execution_service.py \
 backend/modules/platform_change_execution.py \
 backend/jobs/change_execution_worker.py
do
  [ ! -f "$ROOT/$f" ] || { mkdir -p "$BACKUP/$(dirname "$f")"; cp "$ROOT/$f" "$BACKUP/$f"; }
  mkdir -p "$ROOT/$(dirname "$f")"
  cp "$PKG_DIR/$f" "$ROOT/$f"
done
cp "$PKG_DIR/backend/db/migrations/035_change_execution_worker_reconciliation.sql" \
   "$ROOT/backend/db/migrations/035_change_execution_worker_reconciliation.sql"

set -a
source "$ROOT/backend/data/private/cmdb.env"
set +a
PGPASSWORD="$NEXUS_DB_PASSWORD" psql \
  -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" \
  -v ON_ERROR_STOP=1 \
  -f "$ROOT/backend/db/migrations/035_change_execution_worker_reconciliation.sql"

PYTHON_BIN="$ROOT/venv/bin/python"
[ -x "$PYTHON_BIN" ] || PYTHON_BIN="$(command -v python3)"
UNIT_TMP="$(mktemp)"
sed -e "s|__ROOT__|$ROOT|g" -e "s|__PYTHON__|$PYTHON_BIN|g" -e "s|__SERVICE_USER__|$SERVICE_USER|g" \
  "$PKG_DIR/config/systemd/nexus-change-execution-worker.service.in" > "$UNIT_TMP"
sudo cp "$UNIT_TMP" /etc/systemd/system/nexus-change-execution-worker.service
rm -f "$UNIT_TMP"
sudo systemctl daemon-reload
sudo systemctl enable --now nexus-change-execution-worker.service
sudo systemctl restart nexus-api.service
sleep 2
curl -fsS http://127.0.0.1:8080/api/health >/dev/null
echo "Package 046 installed."
echo "Backup: $BACKUP"
