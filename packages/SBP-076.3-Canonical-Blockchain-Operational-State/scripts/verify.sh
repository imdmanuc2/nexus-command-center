#!/usr/bin/env bash
set -euo pipefail

export PYTHONDONTWRITEBYTECODE=1

echo "===== SBP-076.3 VERIFY ====="

python3 - backend/services/blockchain_operations_service.py <<'PY2'
from pathlib import Path
import sys

path = Path(sys.argv[1])
compile(path.read_text(), str(path), "exec")
print("PASS: Python syntax")
PY2

grep -q 'elif running == 1:' \
  backend/services/blockchain_operations_service.py

grep -q 'sync_status and sync_status != "unknown"' \
  backend/services/blockchain_operations_service.py

grep -q 'node_status and node_status != "unknown"' \
  backend/services/blockchain_operations_service.py

grep -q 'node.get("rpc_connected") is True' \
  backend/services/blockchain_operations_service.py

echo "PASS: SBP-076.3 verify"
