#!/usr/bin/env bash
set -euo pipefail

export PYTHONDONTWRITEBYTECODE=1

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PKG="$ROOT/packages/SBP-075.7-Nexus-Provider-Neutral-Blockchain-Node-Projection-Repair"
cd "$ROOT"

echo "===== SBP-075.7 VERIFY ====="

echo
echo "===== PYTHON SYNTAX ====="

PYTHONDONTWRITEBYTECODE=1 \
python3 - \
  backend/db/repositories/seymour_registration_repository.py \
  backend/db/repositories/seymour_telemetry_repository.py \
  tests/test_sbp075_7_provider_neutral_projection.py <<'PY'
from pathlib import Path
import sys

for filename in sys.argv[1:]:
    path = Path(filename)
    compile(path.read_text(), str(path), "exec")
    print("PASS:", path)

print("PASS: Python syntax")
PY

echo
echo "===== NO BCH-SPECIFIC DEFAULT ====="

if grep -n \
  'tel.get("implementation") or "Bitcoin Cash Node"' \
  backend/db/repositories/seymour_registration_repository.py
then
    echo "FAIL: legacy BCH implementation fallback remains"
    exit 1
fi

echo "PASS: provider-neutral implementation fallback"

echo
echo "===== PROVIDER / STATUS CONTRACT ====="

PYTHONDONTWRITEBYTECODE=1 \
python3 - <<'PY'
from backend.db.repositories.seymour_registration_repository import (
    _operational_status,
    _provider_implementation,
)
from backend.db.repositories.seymour_telemetry_repository import (
    _operational_status as telemetry_operational_status,
)

providers = (
    (
        "bitcoin-mainnet",
        "BTC",
        "Bitcoin Core",
    ),
    (
        "bitcoin-cash-mainnet",
        "BCH",
        "Bitcoin Cash Node",
    ),
    (
        "monero-mainnet",
        "XMR",
        "Monero",
    ),
)

for provider, coin, expected in providers:
    actual = _provider_implementation({
        "providerId": provider,
        "coin": coin,
        "telemetry": {},
    })

    print(provider, "=>", actual)
    assert actual == expected

future = _provider_implementation({
    "providerId": "future-mainnet",
    "coin": "FUT",
    "telemetry": {},
})

print("future-mainnet =>", future)

assert future == "FUT Node"
assert future != "Bitcoin Cash Node"

states = (
    (
        {
            "telemetry": {
                "runtimeState": "running",
                "running": True,
            }
        },
        "running",
    ),
    (
        {
            "telemetry": {
                "running": True,
            }
        },
        "running",
    ),
    (
        {
            "telemetry": {
                "running": False,
            }
        },
        "stopped",
    ),
    (
        {
            "telemetry": {
                "installed": False,
            }
        },
        "not-installed",
    ),
    (
        {
            "status": "offline",
            "telemetry": {
                "running": True,
            },
        },
        "stopped",
    ),
)

for asset, expected in states:
    registration = _operational_status(asset)
    telemetry = telemetry_operational_status(asset)

    print(
        "status",
        expected,
        "=>",
        registration,
        "/",
        telemetry,
    )

    assert registration == expected
    assert telemetry == expected

print("PASS: provider mappings")
print("PASS: operational status projection")
PY

echo
echo "===== GENERATED REGRESSION TEST CONTRACT ====="

PYTHONDONTWRITEBYTECODE=1 \
python3 - <<'PY'
import inspect
import runpy

namespace = runpy.run_path(
    "tests/test_sbp075_7_provider_neutral_projection.py"
)

tests = sorted(
    (name, value)
    for name, value in namespace.items()
    if name.startswith("test_")
    and callable(value)
)

assert tests, "no SBP-075.7 regression tests found"

for name, function in tests:
    signature = inspect.signature(function)

    if signature.parameters:
        raise RuntimeError(
            f"{name} unexpectedly requires test fixtures"
        )

    function()
    print("PASS:", name)

print(
    f"PASS: {len(tests)} SBP-075.7 regression tests"
)
PY

echo
echo "===== EXISTING SEYMOUR TEST SOURCE SAFETY ====="

for FILE in \
  tests/test_seymour_registration_contract.py \
  tests/test_seymour_registration_projection.py \
  tests/test_seymour_telemetry_contract.py
do
    test -f "$FILE"

    PYTHONDONTWRITEBYTECODE=1 \
    python3 - "$FILE" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
compile(path.read_text(), str(path), "exec")

print("PASS:", path)
PY
done

echo
echo "===== BYTECODE SAFETY ====="

if find "$PKG" \
  \( -type d -name '__pycache__' \
     -o -type f -name '*.pyc' \
     -o -type f -name '*.pyo' \) \
  -print -quit \
  | grep -q .
then
    echo "FAIL: generated Python artifacts found in package"
    exit 1
fi

echo "PASS: package bytecode-free"

echo
echo "SBP-075.7 VERIFY PASS"
