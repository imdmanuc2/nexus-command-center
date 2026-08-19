#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
cd "$ROOT"

echo "Package 075 verify: managed host discovery foundation"

/usr/bin/python3 - <<'PY'
import json

from backend.services.managed_host_discovery_service import (
    normalize_listening_ports,
    normalize_mounts,
    normalize_network_interfaces,
    normalize_storage_inventory,
    observation_payload,
)

storage = json.dumps({
    "blockdevices": [
        {
            "name": "sda",
            "kname": "sda",
            "path": "/dev/sda",
            "type": "disk",
            "fstype": None,
            "size": 1000000000,
            "mountpoints": [None],
            "model": "Example",
            "serial": "SERIAL",
            "tran": "sata",
            "uuid": None,
            "pkname": None,
            "ro": False,
            "rm": False,
            "children": [
                {
                    "name": "sda1",
                    "kname": "sda1",
                    "path": "/dev/sda1",
                    "type": "part",
                    "fstype": "ext4",
                    "size": 900000000,
                    "mountpoints": ["/"],
                    "model": None,
                    "serial": None,
                    "tran": None,
                    "uuid": "uuid-1",
                    "pkname": "sda",
                    "ro": False,
                    "rm": False
                }
            ]
        }
    ]
})

mounts = json.dumps({
    "filesystems": [
        {
            "source": "/dev/sda1",
            "target": "/",
            "fstype": "ext4",
            "options": "rw"
        },
        {
            "source": "nas:/chains",
            "target": "/mnt/chains",
            "fstype": "nfs4",
            "options": "rw"
        }
    ]
})

interfaces = json.dumps([
    {
        "ifname": "eth0",
        "operstate": "UP",
        "mtu": 1500,
        "address": "aa:bb:cc:dd:ee:ff",
        "addr_info": [
            {
                "family": "inet",
                "local": "192.0.2.20",
                "prefixlen": 24,
                "scope": "global"
            }
        ]
    }
])

ports = (
    "tcp LISTEN 0 4096 0.0.0.0:22 0.0.0.0:*\n"
    "tcp LISTEN 0 4096 0.0.0.0:18080 0.0.0.0:*\n"
)

storage_rows = normalize_storage_inventory(storage)
assert len(storage_rows) == 2
assert storage_rows[1]["mountpoints"] == ["/"]

mount_rows = normalize_mounts(mounts)
assert len(mount_rows) == 2
assert mount_rows[1]["networkStorage"] is True

interface_rows = normalize_network_interfaces(interfaces)
assert interface_rows[0]["addresses"][0]["address"] == "192.0.2.20"

port_rows = normalize_listening_ports(ports)
assert [row["port"] for row in port_rows] == [22, 18080]

observation = observation_payload(
    asset_id="asset-verification-host",
    identity_stdout="Linux verification x86_64",
    storage_stdout=storage,
    mounts_stdout=mounts,
    interfaces_stdout=interfaces,
    ports_stdout=ports,
)

assert observation["source"] == "managed-host-discovery"
assert observation["assetId"] == "asset-verification-host"
assert observation["classification"]["assetType"] == "server"
assert observation["network"]["ip"] == "192.0.2.20"
assert observation["network"]["openPorts"] == [22, 18080]
assert observation["storage"]["mounts"][1]["networkStorage"] is True

print("PASS: storage normalization")
print("PASS: network mount detection")
print("PASS: network interface normalization")
print("PASS: listening port normalization")
print("PASS: discovery observation contract")
PY

python3 - <<'PY'
from backend.capabilities.registry import get_capability_registry
from backend.executors.managed_host_executor import ManagedHostExecutor
from backend.policy.engine import evaluate_operation

required = {
    "host.storage-inventory",
    "host.mounts",
    "host.network-interfaces",
    "host.listening-ports",
}

executor = ManagedHostExecutor()

for capability_id in required:
    capability = get_capability_registry().resolve(capability_id)

    assert capability.requires_approval is False
    assert capability.risk_level == "low"
    assert executor.supports(capability_id, {})
    assert evaluate_operation(capability_id).decision == "allow"

print("PASS: managed-host executor allow-list")
print("PASS: Version 1 read-only policy")
PY

if grep -R \
  -E 'shell=True|/bin/sh|-c["'\'']|command.execute|shell.execute' \
  backend/services/managed_host_discovery_service.py
then
  echo "ERROR: arbitrary shell execution found"
  exit 1
fi

echo "PASS: arbitrary shell execution prohibition"

echo "Package 075 verify: PASS"

/usr/bin/python3 - <<'PY'
import json

import backend.core.reconciliation_engine as reconciliation

from backend.core.observation_engine import (
    normalize_observation,
)

from backend.services.managed_host_discovery_service import (
    observation_payload,
    reconcile_managed_host_discovery,
)

storage = json.dumps({
    "blockdevices": [{
        "name": "nvme0n1",
        "kname": "nvme0n1",
        "path": "/dev/nvme0n1",
        "type": "disk",
        "fstype": None,
        "size": 2000000000000,
        "mountpoints": [None],
        "model": "Example NVMe",
        "serial": "VERIFY123",
        "tran": "nvme",
        "uuid": None,
        "pkname": None,
        "ro": False,
        "rm": False
    }]
})

mounts = json.dumps({
    "filesystems": [{
        "source": "nas:/blockchains",
        "target": "/mnt/blockchains",
        "fstype": "nfs4",
        "options": "rw"
    }]
})

interfaces = json.dumps([{
    "ifname": "eth0",
    "operstate": "UP",
    "mtu": 1500,
    "address": "aa:bb:cc:dd:ee:ff",
    "addr_info": [{
        "family": "inet",
        "local": "192.0.2.55",
        "prefixlen": 24,
        "scope": "global"
    }]
}])

ports = (
    "tcp LISTEN 0 4096 0.0.0.0:22 0.0.0.0:*\n"
    "tcp LISTEN 0 4096 0.0.0.0:8333 0.0.0.0:*\n"
)

payload = observation_payload(
    asset_id="asset-managed-host-verification",
    identity_stdout=(
        "Linux verification-host 6.8.0 #1 SMP "
        "x86_64 GNU/Linux"
    ),
    storage_stdout=storage,
    mounts_stdout=mounts,
    interfaces_stdout=interfaces,
    ports_stdout=ports,
)

assert payload["assetType"] == "server"
assert payload["hostname"] == "verification-host"
assert payload["ip"] == "192.0.2.55"
assert payload["macAddress"] == "aa:bb:cc:dd:ee:ff"
assert payload["openPorts"] == [22, 8333]
assert payload["network"]["openPorts"] == [22, 8333]
assert payload["storage"]["mounts"][0]["networkStorage"] is True

normalized = normalize_observation(
    payload,
    source="managed-host-discovery",
)

assert normalized["identity"]["hostname"] == "verification-host"
assert normalized["identity"]["macAddress"] == "aa:bb:cc:dd:ee:ff"
assert normalized["identity"]["ip"] == "192.0.2.55"
assert normalized["classification"]["assetType"] == "server"
assert normalized["network"]["ip"] == "192.0.2.55"
assert normalized["network"]["openPorts"] == [22, 8333]

print("PASS: observation-engine compatibility")
PY

/usr/bin/python3 - <<'PY'
import json

import backend.core.reconciliation_engine as reconciliation

from backend.services.managed_host_discovery_service import (
    reconcile_managed_host_discovery,
)

captured = {}

original = reconciliation.reconcile_observation

def fake_reconcile(
    payload,
    *,
    source="discovery",
    observer_id="nexus",
    approve_new=False,
    actor_id="nexus",
):
    captured["payload"] = payload
    captured["source"] = source
    captured["observerId"] = observer_id
    captured["approveNew"] = approve_new
    captured["actorId"] = actor_id

    return {
        "status": "pending",
        "decision": "new-candidate",
        "confidence": 0,
        "observation": {},
        "identity": {},
        "asset": None,
    }

reconciliation.reconcile_observation = fake_reconcile

try:
    result = reconcile_managed_host_discovery(
        asset_id="asset-verification",
        identity_stdout=(
            "Linux verify-host 6.8.0 #1 SMP "
            "aarch64 GNU/Linux"
        ),
        storage_stdout=json.dumps({
            "blockdevices": []
        }),
        mounts_stdout=json.dumps({
            "filesystems": []
        }),
        interfaces_stdout=json.dumps([{
            "ifname": "eth0",
            "operstate": "UP",
            "mtu": 1500,
            "address": "00:11:22:33:44:55",
            "addr_info": [{
                "family": "inet",
                "local": "192.0.2.99",
                "prefixlen": 24,
                "scope": "global"
            }]
        }]),
        ports_stdout="",
    )
finally:
    reconciliation.reconcile_observation = original

assert captured["source"] == "managed-host-discovery"
assert captured["observerId"] == "nexus-managed-host"
assert captured["approveNew"] is False
assert captured["payload"]["architecture"] == "arm64"
assert result["status"] == "pending"
assert result["decision"] == "new-candidate"
assert result["discovery"]["approveNew"] is False

print("PASS: reconciliation-engine wiring")
print("PASS: new-host automatic promotion prohibited")
PY

echo "PASS: CMDB reconciliation safety contract"

/usr/bin/python3 - <<'PY'
import json

import backend.services.managed_host_discovery_service as service

captured = {
    "calls": [],
}

def fake_execute(
    capability_id,
    target,
    parameters,
):
    captured["calls"].append({
        "capabilityId": capability_id,
        "target": target,
        "parameters": parameters,
    })

    payloads = {
        "host.identity": (
            "Linux umbrel-test 6.8.0 #1 SMP "
            "aarch64 GNU/Linux\n"
        ),
        "host.storage-inventory": json.dumps({
            "blockdevices": []
        }),
        "host.mounts": json.dumps({
            "filesystems": [{
                "source": "nas:/chains",
                "target": "/mnt/chains",
                "fstype": "nfs4",
                "options": "rw"
            }]
        }),
        "host.network-interfaces": json.dumps([{
            "ifname": "eth0",
            "operstate": "UP",
            "mtu": 1500,
            "address": "00:11:22:33:44:55",
            "addr_info": [{
                "family": "inet",
                "local": "192.0.2.154",
                "prefixlen": 24,
                "scope": "global"
            }]
        }]),
        "host.listening-ports": (
            "tcp LISTEN 0 4096 0.0.0.0:22 0.0.0.0:*\n"
        ),
    }

    return {
        "success": True,
        "stdout": payloads[capability_id],
        "stderr": "",
        "exitCode": 0,
        "durationMs": 1,
    }

original = service.reconcile_managed_host_discovery

def fake_reconcile(**kwargs):
    captured["reconcile"] = kwargs

    return {
        "status": "pending",
        "decision": "new-candidate",
        "asset": None,
    }

service.reconcile_managed_host_discovery = fake_reconcile

try:
    result = service.discover_managed_host(
        target={
            "assetId": "asset-umbrel-test",
            "host": "192.0.2.154",
        },
        execute_capability=fake_execute,
    )
finally:
    service.reconcile_managed_host_discovery = original

expected = [
    "host.identity",
    "host.storage-inventory",
    "host.mounts",
    "host.network-interfaces",
    "host.listening-ports",
]

assert [
    call["capabilityId"]
    for call in captured["calls"]
] == expected

assert all(
    call["parameters"] == {}
    for call in captured["calls"]
)

assert captured["reconcile"]["asset_id"] == (
    "asset-umbrel-test"
)

assert captured["reconcile"]["approve_new"] is False

assert (
    captured["reconcile"]["identity_stdout"]
    .startswith("Linux umbrel-test")
)

assert (
    "nfs4"
    in captured["reconcile"]["mounts_stdout"]
)

assert result["status"] == "ok"
assert result["approveNew"] is False
assert (
    result["reconciliation"]["status"]
    == "pending"
)

print("PASS: discovery orchestration capability sequence")
print("PASS: orchestration remains read-only")
print("PASS: automatic CMDB promotion prohibited")
PY

echo "PASS: managed-host discovery orchestration contract"
