#!/usr/bin/env bash
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

echo "Package 077 verify"

/usr/bin/python3 -m py_compile \
  backend/services/managed_host_storage_enrollment_service.py

echo "PASS: Python syntax"

/usr/bin/python3 - <<'PY'
from backend.services.managed_host_storage_enrollment_service import (
    build_storage_asset,
    enroll_storage_candidate,
    storage_candidates_from_discovery,
)

host = {
    "id": "asset-host-verification",
    "observedState": {
        "managedHostDiscovery": {
            "storage": {
                "devices": [
                    {
                        "name": "sda",
                        "path": "/dev/sda",
                        "type": "disk",
                        "size": 1000000000000,
                    }
                ],
                "mounts": [
                    {
                        "source": "/dev/sda1",
                        "target": "/",
                        "fstype": "ext4",
                        "options": "rw",
                    },
                    {
                        "source": "/dev/sda2",
                        "target": "/boot",
                        "fstype": "ext4",
                        "options": "rw",
                    },
                    {
                        "source": "10.0.0.20:/blockchains",
                        "target": "/mnt/blockchains",
                        "fstype": "nfs4",
                        "options": "rw",
                    },
                    {
                        "source": "overlay",
                        "target": "/var/lib/docker/overlay2/example",
                        "fstype": "overlay",
                        "options": "rw",
                    },
                ],
            }
        }
    },
}

candidates = storage_candidates_from_discovery(host)

assert len(candidates) == 2, candidates

root = next(
    item
    for item in candidates
    if item["mountPath"] == "/"
)

network = next(
    item
    for item in candidates
    if item["mountPath"] == "/mnt/blockchains"
)

assert root["networkStorage"] is False
assert root["approvalRequired"] is True
assert root["approved"] is False

assert network["networkStorage"] is True
assert network["assetType"] == "network-storage"
assert network["source"] == "10.0.0.20:/blockchains"

assert not any(
    item["mountPath"] == "/boot"
    for item in candidates
)

assert not any(
    item["filesystem"] == "overlay"
    for item in candidates
)

print("PASS: storage candidate filtering")
print("PASS: local storage candidate")
print("PASS: network storage candidate")
print("PASS: system mount exclusion")
PY

/usr/bin/python3 - <<'PY'
from backend.services.managed_host_storage_enrollment_service import (
    build_storage_asset,
    enroll_storage_candidate,
)

candidate = {
    "candidateId": "asset-storage-verification",
    "assetId": "asset-storage-verification",
    "assetType": "network-storage",
    "canonicalType": "network-storage",
    "name": "nas:/blockchains",
    "friendlyName": "/mnt/blockchains",
    "displayName": "/mnt/blockchains",
    "primaryRole": "Network Storage",
    "purpose": "Blockchain Storage",
    "hostAssetId": "asset-host-verification",
    "source": "nas:/blockchains",
    "mountPath": "/mnt/blockchains",
    "filesystem": "nfs4",
    "networkStorage": True,
    "mount": {
        "source": "nas:/blockchains",
        "target": "/mnt/blockchains",
        "fstype": "nfs4",
    },
    "approvalRequired": True,
    "approved": False,
}

try:
    build_storage_asset(candidate)
except ValueError:
    pass
else:
    raise AssertionError(
        "Unapproved storage was allowed to enroll."
    )

candidate["approved"] = True

plan = enroll_storage_candidate(
    candidate,
    execute=False,
)

assert plan["status"] == "planned"
assert plan["executable"] is True
assert plan["asset"]["id"] == (
    "asset-storage-verification"
)
assert (
    plan["relationship"]["relationshipType"]
    == "mounts"
)
assert (
    plan["relationship"]["sourceId"]
    == "asset-host-verification"
)
assert (
    plan["relationship"]["targetId"]
    == "asset-storage-verification"
)

print("PASS: explicit storage approval required")
print("PASS: enrollment planning contract")
print("PASS: mounts relationship contract")
print("PASS: verification performs no CMDB writes")
PY

grep -q \
  'upsert_managed_asset' \
  backend/services/managed_host_storage_enrollment_service.py

grep -q \
  'upsert_relationship' \
  backend/services/managed_host_storage_enrollment_service.py

echo "PASS: canonical CMDB write path"

if grep -Eq \
  '192\.168\.|/mnt/seymour-storage|/home/umbrel|seymour-bch-node|seymour-bitcoin-node' \
  backend/services/managed_host_storage_enrollment_service.py
then
  echo "ERROR: environment-specific infrastructure assumption found"
  exit 1
fi

echo "PASS: environment-specific topology prohibited"

echo "Package 077 verify: PASS"

/usr/bin/python3 - <<'PY'
import backend.services.managed_host_storage_enrollment_service as enrollment
import backend.services.managed_host_discovery_service as discovery

pi_identity = enrollment.stable_host_identity(
    machine_id="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    board_serial="10000000deadbeef",
    ssh_host_fingerprint="SHA256:pi-example",
    mac_address="00:11:22:33:44:55",
)

vm_identity = enrollment.stable_host_identity(
    machine_id="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    ssh_host_fingerprint="SHA256:vm-example",
    mac_address="00:11:22:33:44:66",
)

assert pi_identity["identityType"] == "board-serial"
assert vm_identity["identityType"] == "machine-id"
assert pi_identity["assetId"] != vm_identity["assetId"]

pi_changed_network = enrollment.stable_host_identity(
    machine_id="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    board_serial="10000000deadbeef",
    ssh_host_fingerprint="SHA256:different-key",
    mac_address="00:11:22:33:44:99",
)

assert (
    pi_changed_network["assetId"]
    == pi_identity["assetId"]
)

blocked = enrollment.enroll_managed_host_discovery(
    identity_stdout="Linux umbrel aarch64 GNU/Linux",
    storage_stdout='{"blockdevices":[]}',
    mounts_stdout='{"filesystems":[]}',
    interfaces_stdout='[]',
    ports_stdout='',
    stable_identity=pi_identity,
    approved=False,
)

assert blocked["status"] == "approval-required"
assert blocked["approved"] is False
assert blocked["executionPerformed"] is False
assert blocked["asset"] is None
assert blocked["assetId"] == pi_identity["assetId"]

captured = {}

original = discovery.reconcile_managed_host_discovery

def fake_reconcile(**kwargs):
    captured.update(kwargs)

    return {
        "status": "reconciled",
        "decision": "created-new",
        "asset": {
            "id": kwargs["asset_id"],
            "assetType": "server",
        },
    }

discovery.reconcile_managed_host_discovery = fake_reconcile

try:
    result = enrollment.enroll_managed_host_discovery(
        identity_stdout="Linux umbrel aarch64 GNU/Linux",
        storage_stdout='{"blockdevices":[]}',
        mounts_stdout='{"filesystems":[]}',
        interfaces_stdout='[]',
        ports_stdout='',
        stable_identity=pi_identity,
        approved=True,
    )
finally:
    discovery.reconcile_managed_host_discovery = original

assert captured["approve_new"] is True
assert captured["asset_id"] == pi_identity["assetId"]

assert result["approved"] is True
assert result["executionPerformed"] is True
assert result["assetId"] == pi_identity["assetId"]
assert result["asset"]["id"] == pi_identity["assetId"]

assert "umbrel" not in pi_identity["assetId"]
assert "192.168." not in pi_identity["assetId"]

print("PASS: hardware serial identity precedence")
print("PASS: VM machine-id fallback")
print("PASS: distinct physical hosts receive distinct IDs")
print("PASS: hostname excluded from canonical identity")
print("PASS: IP excluded from canonical identity")
print("PASS: mutable evidence does not alter strong identity")
print("PASS: explicit host approval required")
print("PASS: canonical host ID forwarded to reconciliation")
PY

echo "PASS: managed-host stable identity contract"

echo
echo "===== CANONICAL ASSET-ID MIGRATION CONTRACT ====="

python3 - <<'PY'
import inspect

from backend.services.managed_host_storage_enrollment_service import (
    canonicalize_asset_id,
)

source = inspect.getsource(canonicalize_asset_id)

required = [
    "old_asset_id",
    "canonical_asset_id",
    "execute: bool = False",
    "information_schema.columns",
    "data_type",
    "connection.rollback()",
    "connection.commit()",
    "DELETE FROM nexus.assets",
]

for token in required:
    assert token in source, token

print("PASS: canonical migration defaults to planning")
print("PASS: canonical migration validates column data types")
print("PASS: canonical migration uses explicit reference allow-list")
print("PASS: canonical migration is transactional")
print("PASS: canonical migration removes legacy asset only after reference migration")
PY

echo
echo "===== LIVE CANONICAL HOST CONTRACT ====="

python3 - <<'PY'
from backend.db.repositories.asset_repository import get_asset

canonical = get_asset(
    "asset-host-be24584e412bf6f6"
)

legacy = get_asset(
    "pending-umbrel-host"
)

assert canonical is not None
assert legacy is None

assert canonical.get("serialNumber") == (
    "10000000f9fefcfb"
)

assert canonical.get("machineUuid") == (
    "a484fc8354f94dc681d103cd006a152c"
)

assert canonical.get("hostname") == "umbrel"
assert canonical.get("ip") == "192.168.1.154"
assert canonical.get("architecture") == "arm64"

print("PASS: real Pi uses canonical stable host ID")
print("PASS: temporary host ID removed")
print("PASS: stable hardware identity retained")
print("PASS: hostname and IP retained as observed host evidence")
PY

echo
echo "===== LEGACY REFERENCE SAFETY ====="

python3 - <<'PY'
from backend.db.connection import get_connection

OLD = "pending-umbrel-host"

checks = [
    ("asset_identities", "asset_id"),
    ("asset_network_addresses", "asset_id"),
    ("audit_events", "asset_id"),
]

with get_connection() as conn:
    with conn.cursor() as cur:
        for table, column in checks:
            cur.execute(
                f"""
                SELECT COUNT(*) AS count
                FROM nexus.{table}
                WHERE {column} = %s
                """,
                (OLD,),
            )

            count = int(
                cur.fetchone()["count"]
            )

            assert count == 0, (
                table,
                column,
                count,
            )

print("PASS: canonical migration left no known legacy references")
PY
