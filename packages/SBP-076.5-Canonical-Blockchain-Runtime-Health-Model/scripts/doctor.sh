#!/usr/bin/env bash
set -euo pipefail

export PYTHONDONTWRITEBYTECODE=1

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

PKG="packages/SBP-076.5-Canonical-Blockchain-Runtime-Health-Model"
MODEL="$PKG/payload/backend/services/blockchain_runtime_health_service.py"
OPS="backend/services/blockchain_operations_service.py"

echo "===== SBP-076.5 DOCTOR ====="

test -f "$MODEL"
echo "PASS: health-model payload exists"

test -f "$OPS"
echo "PASS: Blockchain Operations service exists"

python3 - "$MODEL" "$OPS" <<'PY'
from pathlib import Path
import sys

for filename in sys.argv[1:]:
    path = Path(filename)

    compile(
        path.read_text(),
        str(path),
        "exec",
    )

    print(
        "PASS: Python syntax",
        path,
    )
PY

python3 - "$MODEL" <<'PY'
from pathlib import Path
import sys

text = Path(sys.argv[1]).read_text()

required = (
    "runtimeState",
    "connectivityState",
    "syncState",
    "rpcState",
    "miningReadiness",
    "overallState",
    "stateReason",
    "SYNCED_THRESHOLD",
)

for token in required:
    assert token in text, token

print("PASS: canonical health dimensions")
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
echo "SBP-076.5 DOCTOR PASS"
