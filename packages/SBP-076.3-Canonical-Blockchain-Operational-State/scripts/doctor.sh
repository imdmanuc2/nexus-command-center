#!/usr/bin/env bash
set -euo pipefail

export PYTHONDONTWRITEBYTECODE=1

PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "===== SBP-076.3 DOCTOR ====="

SERVICE="backend/services/blockchain_operations_service.py"
PATCH="packages/SBP-076.3-Canonical-Blockchain-Operational-State/scripts/patch.py"

test -f "$SERVICE"
echo "PASS: blockchain operations service exists"

test -f "$PATCH"
echo "PASS: patch script exists"

python3 - "$SERVICE" "$PATCH" <<'PY'
from pathlib import Path
import sys

for filename in sys.argv[1:]:
    path = Path(filename)
    compile(
        path.read_text(),
        str(path),
        "exec",
    )
    print("PASS: Python syntax", path)
PY

python3 - "$SERVICE" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()

required = (
    'n.sync_status',
    'n.status',
    'n.peer_count',
    'metrics_by_asset',
    'manager_by_runtime',
    'if running == 0:',
    'elif ibd == 1 and rpc_reachable == 1:',
    'elif running == 1 and rpc_healthy == 1:',
)

for token in required:
    if token not in text:
        raise SystemExit(
            f"FAIL: required pre-install anchor missing: {token}"
        )

print("PASS: pre-install operations contract")
PY

if find "$PKG" \
  \( -type d -name '__pycache__' \
     -o -type f -name '*.pyc' \
     -o -type f -name '*.pyo' \) \
  -print -quit \
  | grep -q .
then
    echo "FAIL: generated Python artifacts found"
    exit 1
fi

echo "PASS: package bytecode-free"
echo "SBP-076.3 DOCTOR PASS"
