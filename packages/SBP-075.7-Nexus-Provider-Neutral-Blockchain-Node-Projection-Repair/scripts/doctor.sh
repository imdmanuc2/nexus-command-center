#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

echo "===== SBP-075.7 DOCTOR ====="

test -f backend/db/repositories/seymour_registration_repository.py
test -f backend/db/repositories/seymour_telemetry_repository.py
test -f backend/data/config/blockchain_provider_catalog.json

python3 -m py_compile \
  backend/db/repositories/seymour_registration_repository.py \
  backend/db/repositories/seymour_telemetry_repository.py

python3 - <<'PY'
import json
from pathlib import Path

data=json.loads(
    Path("backend/data/config/blockchain_provider_catalog.json").read_text()
)
mapping={
    p["providerId"]:p["implementation"]
    for p in data["providers"]
}

assert mapping["bitcoin-mainnet"] == "Bitcoin Core"
assert mapping["bitcoin-cash-mainnet"] == "Bitcoin Cash Node"
assert mapping["monero-mainnet"] == "Monero"

print("Provider catalog canonical mappings: PASS")
PY

echo "SBP-075.7 doctor: PASS"
