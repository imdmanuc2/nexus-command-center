#!/usr/bin/env bash
set -euo pipefail

export PYTHONDONTWRITEBYTECODE=1

echo "===== SBP-076.3 INSTALL ====="

python3 \
  packages/SBP-076.3-Canonical-Blockchain-Operational-State/scripts/patch.py

python3 - backend/services/blockchain_operations_service.py <<'PY2'
from pathlib import Path
import sys

path = Path(sys.argv[1])
compile(path.read_text(), str(path), "exec")
print("PASS: Python syntax")
PY2

echo "PASS: SBP-076.3 install"
