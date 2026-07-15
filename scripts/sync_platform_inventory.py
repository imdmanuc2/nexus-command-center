#!/usr/bin/env python3
"""Synchronize live Nexus API data into PostgreSQL platform inventory tables."""

from __future__ import annotations

import json
from urllib.request import urlopen
from urllib.error import URLError
from typing import Any
from uuid import uuid4

from backend.db.repositories.pool_repository import upsert_pool, list_pools
from backend.db.repositories.worker_repository import upsert_worker
from backend.db.repositories.workload_repository import upsert_workload
from backend.db.repositories.relationship_repository import upsert_relationship


BASE = "http://127.0.0.1:8080"


def fetch(path: str) -> Any:
    with urlopen(BASE + path, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def get_assets() -> list[dict[str, Any]]:
    payload = fetch("/api/cmdb/assets")
    return payload.get("assets", [])


def get_pools() -> list[dict[str, Any]]:
    payload = fetch("/api/mining/pools")
    if isinstance(payload, list):
        return payload
    return payload.get("pools") or payload.get("data") or []


def get_workers() -> list[dict[str, Any]]:
    payload = fetch("/api/mining/workers")
    if isinstance(payload, list):
        return payload
    return payload.get("workers") or payload.get("data") or []


def normalize_pool(raw: dict[str, Any]) -> dict[str, Any]:
    host = str(raw.get("host") or raw.get("poolHost") or raw.get("apiHost") or "")
    api_port = raw.get("apiPort") or raw.get("port") or 4000
    native = str(raw.get("nativePoolId") or raw.get("poolId") or raw.get("id") or "unknown")
    pool_id = str(raw.get("poolInstanceId") or raw.get("nexusPoolId") or f"pool-{host.replace('.', '-')}-{api_port}-{native}")
    return {
        "poolId": pool_id,
        "nativePoolId": native,
        "name": raw.get("name") or raw.get("poolName") or native,
        "coin": raw.get("coin") or raw.get("symbol") or "UNKNOWN",
        "mode": raw.get("mode") or ("public" if raw.get("public") else "solo"),
        "visibility": raw.get("visibility") or ("public" if raw.get("public") else "private"),
        "status": raw.get("status") or ("online" if raw.get("online", True) else "offline"),
        "host": host,
        "apiPort": api_port,
        "apiBase": raw.get("apiBase") or raw.get("apiUrl") or "",
        "stratumPorts": raw.get("stratumPorts") or [],
        "observedState": raw,
    }


def classify_worker(raw: dict[str, Any], asset: dict[str, Any] | None) -> tuple[str, str]:
    asset_type = (asset or {}).get("assetType")
    if asset_type == "asic":
        return "asic", "ASIC"
    if asset_type == "virtual-machine":
        capabilities = set((asset or {}).get("capabilities") or [])
        if "gpu-compute" in capabilities:
            return "gpu", "Virtual"
        return "cpu", "Virtual"
    if asset_type == "compute-host":
        capabilities = set((asset or {}).get("capabilities") or [])
        if "gpu-compute" in capabilities or "gpu-mining" in capabilities:
            return "gpu", "GPU"
        return "cpu", "CPU"
    return str(raw.get("workerType") or "unknown"), str(raw.get("hardwareType") or "Unknown")


def main() -> int:
    assets = get_assets()
    assets_by_worker = {
        str(asset.get("workerId")).strip().lower(): asset
        for asset in assets
        if asset.get("workerId")
    }

    assets_by_name = {
        str(
            asset.get("friendlyName")
            or asset.get("displayName")
            or asset.get("name")
            or ""
        ).strip().lower(): asset
        for asset in assets
    }

    pool_records = []
    for raw_pool in get_pools():
        pool = normalize_pool(raw_pool)
        upsert_pool(pool)
        pool_records.append(pool)

    pools_by_native_host = {
        (str(pool.get("nativePoolId")), str(pool.get("host"))): pool
        for pool in pool_records
    }

    worker_count = 0
    workload_count = 0
    relationship_count = 0

    for raw in get_workers():
        source_worker_id = str(
            raw.get("sourceWorkerId")
            or raw.get("workerId")
            or raw.get("id")
            or raw.get("name")
            or ""
        ).strip()

        if not source_worker_id:
            continue

        # MiningCore worker identities may be wallet.worker, address.worker,
        # or another namespace followed by the local worker suffix.
        worker_suffix = source_worker_id.rsplit(".", 1)[-1].strip().lower()

        display_name = str(
            raw.get("displayName")
            or raw.get("friendlyName")
            or raw.get("name")
            or source_worker_id
        ).strip()

        asset = (
            assets_by_worker.get(source_worker_id.lower())
            or assets_by_worker.get(worker_suffix)
            or assets_by_name.get(display_name.lower())
        )

        worker_type, hardware_type = classify_worker(raw, asset)

        raw_pool_id = str(
            raw.get("poolInstanceId")
            or raw.get("nativePoolId")
            or raw.get("poolId")
            or ""
        ).strip()

        pool_host = str(
            raw.get("poolHost")
            or raw.get("host")
            or ""
        ).strip()

        pool = None

        # Current worker API may already return the canonical Nexus
        # pool-instance ID.
        if raw_pool_id.startswith("pool-"):
            pool = next(
                (
                    candidate
                    for candidate in pool_records
                    if candidate.get("poolId") == raw_pool_id
                ),
                None,
            )

        # Otherwise treat it as MiningCore's native local pool ID.
        if pool is None:
            pool = pools_by_native_host.get(
                (raw_pool_id, pool_host)
            )

        if pool is None:
            matches = [
                candidate
                for candidate in pool_records
                if candidate.get("nativePoolId") == raw_pool_id
            ]
            pool = matches[0] if len(matches) == 1 else None

        native_pool_id = str(
            (pool or {}).get("nativePoolId")
            or (
                raw_pool_id
                if not raw_pool_id.startswith("pool-")
                else ""
            )
        )

        canonical_worker_id = str(
            raw.get("nexusWorkerId")
            or f"worker-{(pool or {}).get('poolId', 'unassigned')}-{source_worker_id}"
        )

        worker = {
            "workerId": canonical_worker_id,
            "sourceWorkerId": source_worker_id,
            "sourceSystem": "miningcore",
            "workerType": worker_type,
            "hardwareType": hardware_type,
            "displayName": display_name,
            "assetId": (asset or {}).get("id"),
            "assetMatched": bool(asset),
            "reconciliationStatus": "matched" if asset else "unmatched",
            "poolId": native_pool_id,
            "nativePoolId": native_pool_id,
            "poolInstanceId": (pool or {}).get("poolId"),
            "poolHost": pool_host,
            "coin": raw.get("coin") or (pool or {}).get("coin"),
            "status": raw.get("status") or ("online" if raw.get("online", True) else "offline"),
            "currentHashrate": raw.get("hashrate") or raw.get("currentHashrate"),
            "hashrateUnit": raw.get("hashrateUnit") or "H/s",
            "sharesPerSecond": raw.get("sharesPerSecond"),
            "acceptedShares": raw.get("acceptedShares"),
            "rejectedShares": raw.get("rejectedShares"),
            "lastShareAt": raw.get("lastShareAt"),
            "classificationSource": "cmdb-match" if asset else "miningcore",
            "classificationConfidence": 100 if asset else 50,
            "identity": {
                "sourceWorkerId": source_worker_id,
                "workerSuffix": worker_suffix,
            },
            "observedState": raw,
        }
        upsert_worker(worker)
        worker_count += 1

        workload_id = f"workload-{canonical_worker_id}-crypto-mining"
        workload = {
            "workloadId": workload_id,
            "assetId": (asset or {}).get("id"),
            "workerId": canonical_worker_id,
            "workloadType": "crypto-mining",
            "name": f"{worker['displayName']} Mining",
            "status": worker["status"],
            "runtime": "native",
            "software": raw.get("software") or "MiningCore worker",
            "coin": worker["coin"],
            "poolId": native_pool_id,
            "nativePoolId": native_pool_id,
            "poolInstanceId": worker["poolInstanceId"],
            "observedState": raw,
        }
        upsert_workload(workload)
        workload_count += 1

        if asset:
            upsert_relationship({
                "relationshipId": f"relationship-{uuid4().hex}",
                "sourceType": "worker",
                "sourceId": canonical_worker_id,
                "relationshipType": "runs-on",
                "targetType": "asset",
                "targetId": asset["id"],
                "source": "platform-inventory-sync",
                "observed": True,
                "approved": True,
            })
            relationship_count += 1

        if pool:
            upsert_relationship({
                "relationshipId": f"relationship-{uuid4().hex}",
                "sourceType": "worker",
                "sourceId": canonical_worker_id,
                "relationshipType": "mines-on",
                "targetType": "pool",
                "targetId": pool["poolId"],
                "source": "platform-inventory-sync",
                "observed": True,
                "approved": True,
            })
            relationship_count += 1

            upsert_relationship({
                "relationshipId": f"relationship-{uuid4().hex}",
                "sourceType": "workload",
                "sourceId": workload_id,
                "relationshipType": "uses-pool",
                "targetType": "pool",
                "targetId": pool["poolId"],
                "source": "platform-inventory-sync",
                "observed": True,
                "approved": True,
            })
            relationship_count += 1

    print(json.dumps({
        "pools": len(pool_records),
        "workers": worker_count,
        "workloads": workload_count,
        "relationshipsWritten": relationship_count,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
