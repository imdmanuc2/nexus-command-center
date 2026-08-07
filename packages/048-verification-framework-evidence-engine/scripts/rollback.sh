#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

sudo systemctl disable --now nexus-verification-worker.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/nexus-verification-worker.service
sudo systemctl daemon-reload

/usr/bin/python3 - <<'PY'
from pathlib import Path

path = Path("backend/api/server.py")
text = path.read_text()
text = text.replace("from backend.modules import platform_verifications\n", "")
for begin, end in (
    ("        # PACKAGE-048-VERIFICATION-GET-BEGIN\n", "        # PACKAGE-048-VERIFICATION-GET-END\n"),
    ("        # PACKAGE-048-VERIFICATION-POST-BEGIN\n", "        # PACKAGE-048-VERIFICATION-POST-END\n"),
):
    while begin in text and end in text:
        start = text.index(begin)
        finish = text.index(end, start) + len(end)
        if finish < len(text) and text[finish:finish + 1] == "\n":
            finish += 1
        text = text[:start] + text[finish:]
path.write_text(text)
PY

set -a
source backend/data/private/cmdb.env
set +a
export PGPASSWORD="$NEXUS_DB_PASSWORD"
psql -v ON_ERROR_STOP=1 -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" \
  -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" <<'SQL'
BEGIN;
DROP TABLE IF EXISTS nexus.verification_events;
DROP TABLE IF EXISTS nexus.verification_evidence;
DROP TABLE IF EXISTS nexus.verification_step_runs;
DROP TABLE IF EXISTS nexus.verification_runs;
DROP TABLE IF EXISTS nexus.verification_profile_steps;
DROP TABLE IF EXISTS nexus.verification_profiles;
COMMIT;
SQL

sudo systemctl restart nexus-api.service
echo "Package 048 rollback complete."
