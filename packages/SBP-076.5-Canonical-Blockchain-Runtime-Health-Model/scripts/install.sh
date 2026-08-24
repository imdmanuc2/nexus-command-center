#!/usr/bin/env bash
set -euo pipefail

export PYTHONDONTWRITEBYTECODE=1

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

PKG="packages/SBP-076.5-Canonical-Blockchain-Runtime-Health-Model"

MODEL_SOURCE="$PKG/payload/backend/services/blockchain_runtime_health_service.py"
MODEL_TARGET="backend/services/blockchain_runtime_health_service.py"
OPS="backend/services/blockchain_operations_service.py"

echo "===== SBP-076.5 INSTALL ====="

"$PKG/scripts/doctor.sh"
"$PKG/scripts/verify-model.sh"

mkdir -p "$PKG/backups"

cp "$OPS" \
  "$PKG/backups/blockchain_operations_service.py"

install -m 0644 \
  "$MODEL_SOURCE" \
  "$MODEL_TARGET"

python3 \
  "$PKG/scripts/integrate_operations.py"

python3 - "$MODEL_TARGET" "$OPS" <<'PY'
from pathlib import Path
import sys

for filename in sys.argv[1:]:
    path = Path(filename)
    compile(path.read_text(), str(path), "exec")
    print("PASS: Python syntax", path)
PY

echo "SBP-076.5 INSTALL PASS"
