#!/usr/bin/env bash
set -euo pipefail
PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; ROOT="$(cd "$PKG_DIR/../.." && pwd)"; STAMP="$(date +%Y%m%d-%H%M%S)"; BACKUP="$ROOT/packages/backups/047-change-rollback-$STAMP"; SERVICE_USER="${SUDO_USER:-$(id -un)}"
mkdir -p "$BACKUP/backend/api"; cp "$ROOT/backend/api/server.py" "$BACKUP/backend/api/server.py"
sudo systemctl stop nexus-change-rollback-worker.service 2>/dev/null || true
install -m 0644 "$PKG_DIR/backend/db/repositories/change_rollback_repository.py" "$ROOT/backend/db/repositories/change_rollback_repository.py"
install -m 0644 "$PKG_DIR/backend/services/change_rollback_service.py" "$ROOT/backend/services/change_rollback_service.py"
install -m 0644 "$PKG_DIR/backend/modules/platform_change_rollback.py" "$ROOT/backend/modules/platform_change_rollback.py"
install -m 0644 "$PKG_DIR/backend/jobs/change_rollback_worker.py" "$ROOT/backend/jobs/change_rollback_worker.py"
install -m 0755 "$PKG_DIR/backend/api/install_change_rollback_routes.py" "$ROOT/backend/api/install_change_rollback_routes.py"
python3 "$ROOT/backend/api/install_change_rollback_routes.py"
grep -q 'from backend.modules import platform_change_rollback' "$ROOT/backend/api/server.py"
grep -q '/api/change-rollbacks/status' "$ROOT/backend/api/server.py"
grep -q '/api/change-rollbacks/history' "$ROOT/backend/api/server.py"
grep -q '/api/change-rollbacks/approve' "$ROOT/backend/api/server.py"
grep -q '/api/change-rollbacks/queue' "$ROOT/backend/api/server.py"
python3 -m py_compile "$ROOT/backend/api/server.py"
install -m 0644 "$PKG_DIR/backend/db/migrations/036_change_rollback_orchestration_recovery.sql" "$ROOT/backend/db/migrations/036_change_rollback_orchestration_recovery.sql"
set -a; source "$ROOT/backend/data/private/cmdb.env"; set +a
PGPASSWORD="$NEXUS_DB_PASSWORD" psql -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" -v ON_ERROR_STOP=1 -f "$ROOT/backend/db/migrations/036_change_rollback_orchestration_recovery.sql"
PYTHON_BIN="$ROOT/venv/bin/python"; [ -x "$PYTHON_BIN" ] || PYTHON_BIN="$(command -v python3)"; TMP="$(mktemp)"
sed -e "s|__ROOT__|$ROOT|g" -e "s|__PYTHON__|$PYTHON_BIN|g" -e "s|__SERVICE_USER__|$SERVICE_USER|g" "$PKG_DIR/config/systemd/nexus-change-rollback-worker.service.in" > "$TMP"
sudo cp "$TMP" /etc/systemd/system/nexus-change-rollback-worker.service; rm -f "$TMP"; sudo systemctl daemon-reload; sudo systemctl enable --now nexus-change-rollback-worker.service; sudo systemctl restart nexus-api.service; sleep 2; curl -fsS http://127.0.0.1:8080/api/health >/dev/null
echo 'Package 047 installed.'; echo "Backup: $BACKUP"
