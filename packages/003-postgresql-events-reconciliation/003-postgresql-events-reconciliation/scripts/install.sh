#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
cd "$PROJECT_ROOT"
mkdir -p backend/db/repositories
for f in backend/core/cmdb_audit.py backend/core/observation_engine.py; do
  [[ -f "$f" ]] && cp "$f" "$f.before-postgresql-$STAMP"
done
cp "$PACKAGE_ROOT/backend/db/repositories/"*.py backend/db/repositories/
cp "$PACKAGE_ROOT/backend/core/cmdb_audit.py" backend/core/cmdb_audit.py
cp "$PACKAGE_ROOT/backend/core/observation_engine.py" backend/core/observation_engine.py
cp "$PACKAGE_ROOT/scripts/import_legacy_audit.py" scripts/import_legacy_audit.py
cp "$PACKAGE_ROOT/scripts/import_legacy_observations.py" scripts/import_legacy_observations.py
chmod +x scripts/import_legacy_*.py
python3 -m py_compile backend/db/repositories/*.py backend/core/cmdb_audit.py backend/core/observation_engine.py
python3 -m scripts.import_legacy_audit
python3 -m scripts.import_legacy_observations
echo "Package 003 installed."
