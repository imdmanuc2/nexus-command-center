#!/usr/bin/env bash
set -euo pipefail

export PYTHONDONTWRITEBYTECODE=1

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

PKG="packages/SBP-076.5-Canonical-Blockchain-Runtime-Health-Model"

MODEL="backend/services/blockchain_runtime_health_service.py"
OPS="backend/services/blockchain_operations_service.py"

echo "===== SBP-076.5 VERIFY ====="

python3 - "$MODEL" "$OPS" <<'PY'
from pathlib import Path
import sys

for filename in sys.argv[1:]:
    path = Path(filename)
    compile(path.read_text(), str(path), "exec")
    print("PASS: Python syntax", path)
PY

grep -q \
  'derive_blockchain_runtime_health' \
  "$OPS"

echo "PASS: canonical health model imported"

for FIELD in \
  runtimeState \
  connectivityState \
  syncState \
  rpcState \
  miningReadiness \
  overallState \
  stateReason
do
    grep -q "\"$FIELD\"" "$OPS"
done

echo "PASS: canonical health dimensions projected"

for FIELD in \
  '"state"' \
  '"nodeStatus"' \
  '"syncStatus"' \
  '"syncProgress"' \
  '"running"' \
  '"manager"'
do
    grep -q "$FIELD" "$OPS"
done

echo "PASS: backward-compatible fields preserved"

if find "$PKG" \
  \( -type d -name '__pycache__' \
     -o -type f -name '*.pyc' \
     -o -type f -name '*.pyo' \) \
  -print -quit | grep -q .
then
    echo "FAIL: generated Python artifacts found"
    exit 1
fi

echo "PASS: package bytecode-free"
echo "SBP-076.5 VERIFY PASS"
