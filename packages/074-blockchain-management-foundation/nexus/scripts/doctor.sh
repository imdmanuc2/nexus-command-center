#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
cd "$ROOT"

echo "Package 074 doctor: Blockchain Management Foundation"

for path in \
  backend/data/config/blockchain_provider_catalog.json \
  backend/services/blockchain_management_service.py \
  backend/modules/blockchain_management.py
do
  test -f "$path"
  echo "PASS: $path"
done

/usr/bin/python3 -m py_compile \
  backend/services/blockchain_management_service.py \
  backend/modules/blockchain_management.py

/usr/bin/python3 - <<'PY'
import json
from pathlib import Path

path = Path(
    "backend/data/config/blockchain_provider_catalog.json"
)

data = json.loads(path.read_text())

ids = {
    item["providerId"]
    for item in data["providers"]
}

required = {
    "bitcoin-mainnet",
    "bitcoin-cash-mainnet",
    "monero-mainnet",
}

assert required <= ids
print("PASS: provider catalog contract")
PY

echo "Package 074 doctor: PASS"
