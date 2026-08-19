#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
cd "$ROOT"

echo "Package 075 doctor: managed host discovery foundation"

for command in \
  /usr/bin/lsblk \
  /usr/bin/findmnt \
  /usr/sbin/ip \
  /usr/bin/ss
do
  if [[ -x "$command" ]]; then
    echo "PASS: $command"
  else
    echo "ERROR: required discovery command missing: $command"
    exit 1
  fi
done

/usr/bin/python3 -m py_compile \
  backend/capabilities/registry.py \
  backend/executors/managed_host_executor.py \
  backend/policy/engine.py \
  backend/services/managed_host_discovery_service.py

echo "PASS: Python syntax"

python3 - <<'PY'
from backend.capabilities.registry import (
    get_capability_registry,
)

registry = get_capability_registry()

required = {
    "host.storage-inventory",
    "host.mounts",
    "host.network-interfaces",
    "host.listening-ports",
}

available = {
    item["capabilityId"]
    for item in registry.describe()
}

assert required <= available

for capability_id in required:
    item = registry.resolve(capability_id)
    assert item.risk_level == "low"
    assert item.requires_approval is False
    assert not item.allowed_parameters

print("PASS: read-only discovery capability registry")
PY

echo "Package 075 doctor: PASS"
