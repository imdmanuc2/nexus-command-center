"""Synchronize configured generic Stratum pools into PostgreSQL.

This supports pool software that does not expose a MiningCore-compatible
API. It normalizes configured pools, workers, workloads, and topology
relationships into the same Nexus Platform model used by native connectors.
"""

from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.db.repositories.pool_repository import upsert_pool
from backend.db.repositories.worker_repository import upsert_worker
from backend.db.repositories.workload_repository import upsert_workload
from backend.db.repositories.relationship_repository import (
    upsert_relationship,
)


CONFIG_PATH = Path(
    "backend/data/config/generic_stratum_pools.json"
)


def _load_config() -> list[dict[str, Any]]:
    if not CONFIG_PATH.exists():
        return []

    payload = json.loads(
        CONFIG_PATH.read_text(encoding="utf-8")
    )

    pools = payload.get("pools", [])

    if not isinstance(pools, list):
        raise ValueError(
            "generic_stratum_pools.json requires a pools array."
        )

    return [
        pool
        for pool in pools
        if isinstance(pool, dict)
        and pool.get("enabled", True)
    ]


def _port_reachable(
    host: str,
    port: int,
    timeout: float = 1.5,
) -> bool:
    try:
        with socket.create_connection(
            (host, int(port)),
            timeout=timeout,
        ):
            return True
    except (OSError, ValueError):
        return False


def _relationship(
    *,
    source_type: str,
    source_id: str,
    relationship_type: str,
    target_type: str,
    target_id: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    upsert_relationship({
        "relationshipId": f"relationship-{uuid4().hex}",
        "sourceType": source_type,
        "sourceId": source_id,
        "relationshipType": relationship_type,
        "targetType": target_type,
        "targetId": target_id,
        "status": "active",
        "source": "generic-stratum-sync",
        "observed": True,
        "approved": True,
        "metadata": metadata or {},
    })


def synchronize_generic_stratum_inventory() -> dict[str, Any]:
    configured_pools = _load_config()

    result = {
        "status": "ok",
        "source": "generic-stratum-sync",
        "configuredPools": len(configured_pools),
        "poolsWritten": 0,
        "workersWritten": 0,
        "workloadsWritten": 0,
        "relationshipsWritten": 0,
        "items": [],
    }

    for configured in configured_pools:
        pool_id = str(
            configured.get("poolId") or ""
        ).strip()

        host = str(
            configured.get("host") or ""
        ).strip()

        coin = str(
            configured.get("coin") or "UNKNOWN"
        ).strip().upper()

        native_pool_id = str(
            configured.get("nativePoolId")
            or coin.lower()
        ).strip()

        stratum_ports = [
            int(port)
            for port in configured.get(
                "stratumPorts",
                [],
            )
        ]

        if not pool_id:
            raise ValueError(
                "Generic Stratum pool requires poolId."
            )

        if not host:
            raise ValueError(
                f"Generic Stratum pool {pool_id} requires host."
            )

        port_health = {
            str(port): _port_reachable(host, port)
            for port in stratum_ports
        }

        reachable_ports = [
            int(port)
            for port, reachable in port_health.items()
            if reachable
        ]

        pool_online = bool(reachable_ports)

        configured_workers = configured.get(
            "workers",
            [],
        )

        pool = {
            "poolId": pool_id,
            "nativePoolId": native_pool_id,
            "name": (
                configured.get("name")
                or f"{coin} Stratum Pool"
            ),
            "instanceName": (
                configured.get("instanceName")
                or configured.get("software")
                or "Generic Stratum"
            ),
            "coin": coin,
            "mode": configured.get("mode") or "solo",
            "visibility": (
                configured.get("visibility")
                or "private"
            ),
            "status": (
                "active"
                if pool_online
                else "offline"
            ),
            "host": host,
            "apiPort": None,
            "apiBase": "",
            "stratumPorts": stratum_ports,
            "configuration": {
                "software": (
                    configured.get("software")
                    or "generic-stratum"
                ),
                "connectorType": "generic-stratum",
                "blockchainAssetId": (
                    configured.get(
                        "blockchainAssetId"
                    )
                ),
            },
            "observedState": {
                "software": (
                    configured.get("software")
                    or "generic-stratum"
                ),
                "connectorType": "generic-stratum",
                "host": host,
                "stratumPorts": stratum_ports,
                "reachablePorts": reachable_ports,
                "portHealth": port_health,
                "configuredWorkerCount": len(
                    configured_workers
                ),
                "online": pool_online,
            },
            "metadata": {
                "managedBy": "nexus",
                "inventorySource": (
                    "generic-stratum-config"
                ),
            },
        }

        upsert_pool(pool)
        result["poolsWritten"] += 1

        blockchain_asset_id = str(
            configured.get("blockchainAssetId")
            or ""
        ).strip()

        if blockchain_asset_id:
            _relationship(
                source_type="pool",
                source_id=pool_id,
                relationship_type="depends-on",
                target_type="asset",
                target_id=blockchain_asset_id,
                metadata={
                    "dependencyType": "blockchain-rpc",
                    "coin": coin,
                    "active": pool_online,
                },
            )
            result["relationshipsWritten"] += 1

        worker_items = []

        for worker_config in configured_workers:
            if not isinstance(worker_config, dict):
                continue

            source_worker_id = str(
                worker_config.get("sourceWorkerId")
                or worker_config.get("walletAddress")
                or ""
            ).strip()

            if not source_worker_id:
                continue

            worker_name = str(
                worker_config.get("workerName")
                or source_worker_id
            ).strip()

            display_name = str(
                worker_config.get("displayName")
                or worker_name
            ).strip()

            asset_id = (
                worker_config.get("assetId")
                or None
            )

            configured_active = bool(
                worker_config.get("active", True)
            )

            connection_confirmed = bool(
                worker_config.get("connectionConfirmed", False)
            )
            telemetry_available = bool(
                worker_config.get("telemetryAvailable", False)
            )
            measurable_hashrate = float(
                worker_config.get("currentHashrate") or 0
            ) > 0
            recent_share = bool(
                worker_config.get("lastShareAt")
                or worker_config.get("acceptedShares")
            )

            live_activity = bool(
                connection_confirmed
                or measurable_hashrate
                or recent_share
            )

            worker_online = bool(
                pool_online
                and configured_active
                and live_activity
            )

            canonical_worker_id = (
                f"worker-{pool_id}-"
                f"{source_worker_id}"
            )

            worker = {
                "workerId": canonical_worker_id,
                "sourceWorkerId": source_worker_id,
                "sourceSystem": "generic-stratum",
                "workerType": (
                    worker_config.get("workerType")
                    or "unknown"
                ),
                "hardwareType": (
                    worker_config.get("hardwareType")
                    or "Unknown"
                ),
                "displayName": display_name,
                "assetId": asset_id,
                "assetMatched": bool(asset_id),
                "reconciliationStatus": (
                    "matched"
                    if asset_id
                    else "unmatched"
                ),
                "poolId": native_pool_id,
                "nativePoolId": native_pool_id,
                "poolInstanceId": pool_id,
                "poolHost": host,
                "poolApiPort": None,
                "workerName": worker_name,
                "minerAddress": source_worker_id,
                "coin": coin,
                "status": (
                    "online"
                    if worker_online
                    else "unknown"
                ),
                "activityState": (
                    "active"
                    if worker_online
                    else "unknown"
                ),
                "connectionConfirmed": connection_confirmed,
                "telemetryAvailable": telemetry_available,
                "currentHashrate": (
                    worker_config.get("currentHashrate")
                    if worker_online
                    else 0
                ),
                "hashrateUnit": "H/s",
                "sharesPerSecond": (
                    worker_config.get("sharesPerSecond")
                    if worker_online
                    else 0
                ),
                "acceptedShares": worker_config.get("acceptedShares"),
                "rejectedShares": worker_config.get("rejectedShares"),
                "lastShareAt": worker_config.get("lastShareAt"),
                "classificationSource": (
                    "operator-configured"
                ),
                "classificationConfidence": 100,
                "identity": {
                    "sourceWorkerId": source_worker_id,
                    "workerName": worker_name,
                    "minerAddress": source_worker_id,
                },
                "observedState": {
                    "configuredActive": (
                        configured_active
                    ),
                    "poolReachable": pool_online,
                    "liveWorkerTelemetry": telemetry_available,
                    "connectionConfirmed": connection_confirmed,
                    "telemetryAvailable": telemetry_available,
                    "activityState": (
                        "active"
                        if worker_online
                        else "unknown"
                    ),
                    "evidence": (
                        "live-activity-confirmed"
                        if worker_online
                        else "remembered-username-only"
                    ),
                },
                "metadata": {
                    "software": (
                        configured.get("software")
                        or "generic-stratum"
                    ),
                    "telemetryAvailable": False,
                },
            }

            upsert_worker(worker)
            result["workersWritten"] += 1

            workload_id = (
                f"workload-{canonical_worker_id}"
                "-crypto-mining"
            )

            workload = {
                "workloadId": workload_id,
                "assetId": asset_id,
                "workerId": canonical_worker_id,
                "workloadType": "crypto-mining",
                "name": f"{display_name} Mining",
                "status": worker["status"],
                "runtime": "native",
                "software": (
                    configured.get("software")
                    or "Generic Stratum worker"
                ),
                "version": "",
                "coin": coin,
                "poolId": native_pool_id,
                "nativePoolId": native_pool_id,
                "poolInstanceId": pool_id,
                "configuration": {
                    "poolHost": host,
                    "stratumPorts": stratum_ports,
                    "workerName": worker_name,
                },
                "observedState": (
                    worker["observedState"]
                ),
                "metadata": {
                    "inventorySource": (
                        "generic-stratum-config"
                    ),
                },
            }

            upsert_workload(workload)
            result["workloadsWritten"] += 1

            if asset_id:
                _relationship(
                    source_type="worker",
                    source_id=canonical_worker_id,
                    relationship_type="runs-on",
                    target_type="asset",
                    target_id=asset_id,
                    metadata={
                        "active": worker_online,
                    },
                )
                result["relationshipsWritten"] += 1

            _relationship(
                source_type="worker",
                source_id=canonical_worker_id,
                relationship_type="mines-on",
                target_type="pool",
                target_id=pool_id,
                metadata={
                    "active": worker_online,
                    "activityKind": "shares",
                    "configured": True,
                    "telemetryAvailable": False,
                    "coin": coin,
                },
            )
            result["relationshipsWritten"] += 1

            _relationship(
                source_type="workload",
                source_id=workload_id,
                relationship_type="uses-pool",
                target_type="pool",
                target_id=pool_id,
                metadata={
                    "active": worker_online,
                    "activityKind": "shares",
                    "configured": True,
                },
            )
            result["relationshipsWritten"] += 1

            worker_items.append({
                "workerId": canonical_worker_id,
                "displayName": display_name,
                "assetId": asset_id,
                "status": worker["status"],
            })

        result["items"].append({
            "poolId": pool_id,
            "host": host,
            "status": pool["status"],
            "reachablePorts": reachable_ports,
            "workers": worker_items,
        })

    return result
