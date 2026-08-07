"""Synchronize configured generic Stratum pools into PostgreSQL.

This supports pool software that does not expose a MiningCore-compatible
API. It normalizes configured pools, workers, workloads, and topology
relationships into the same Nexus Platform model used by native connectors.
"""

from __future__ import annotations

import json
import socket
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.request import Request, urlopen
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


def _fetch_json(url: str, timeout: float = 3.0) -> dict[str, Any] | None:
    if not url:
        return None
    try:
        request = Request(url, headers={"Accept": "application/json"})
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload if isinstance(payload, dict) else None
    except (OSError, URLError, ValueError, json.JSONDecodeError):
        return None


def _telemetry_worker_map(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not payload:
        return {}
    workers = payload.get("workers", [])
    if not isinstance(workers, list):
        return {}
    return {
        str(item.get("sourceWorkerId") or "").strip(): item
        for item in workers
        if isinstance(item, dict) and str(item.get("sourceWorkerId") or "").strip()
    }


def _relationship(
    *,
    source_type: str,
    source_id: str,
    relationship_type: str,
    target_type: str,
    target_id: str,
    active: bool = True,
    metadata: dict[str, Any] | None = None,
) -> None:
    upsert_relationship({
        "relationshipId": f"relationship-{uuid4().hex}",
        "sourceType": source_type,
        "sourceId": source_id,
        "relationshipType": relationship_type,
        "targetType": target_type,
        "targetId": target_id,
        "status": "active" if active else "inactive",
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

        telemetry_url = str(configured.get("telemetryUrl") or "").strip()
        telemetry_payload = _fetch_json(telemetry_url)
        telemetry_workers = _telemetry_worker_map(telemetry_payload)
        telemetry_pool = (
            telemetry_payload.get("pool", {})
            if isinstance(telemetry_payload, dict)
            else {}
        )
        telemetry_available_for_pool = bool(telemetry_payload)

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
                "telemetryUrl": telemetry_url,
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
                "telemetryAvailable": telemetry_available_for_pool,
                "telemetry": telemetry_pool,
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

            telemetry_worker = telemetry_workers.get(
                source_worker_id,
                {},
            )
            connection_confirmed = bool(
                telemetry_worker.get("connectionConfirmed", False)
            )
            telemetry_available = bool(
                telemetry_worker.get("telemetryAvailable", False)
            )
            current_hashrate = float(
                telemetry_worker.get("currentHashrate") or 0
            )
            last_share_at = telemetry_worker.get("lastShareAt")
            live_activity = bool(
                telemetry_worker.get("online", False)
                and connection_confirmed
                and current_hashrate > 0
                and last_share_at
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
                    current_hashrate
                    if worker_online
                    else 0
                ),
                "hashrateUnit": "H/s",
                "sharesPerSecond": (
                    telemetry_worker.get("sharesPerSecond1m", 0)
                    if worker_online
                    else 0
                ),
                "acceptedShares": telemetry_worker.get("acceptedShares"),
                "rejectedShares": telemetry_worker.get("rejectedShares"),
                "lastShareAt": last_share_at,
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
                    "telemetryAvailable": telemetry_available,
                    "telemetryUrl": telemetry_url,
                    "lastShareAgeSeconds": telemetry_worker.get("lastShareAgeSeconds"),
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
                    active=worker_online,
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
                    "telemetryAvailable": telemetry_available,
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
                active=worker_online,
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
            "telemetryAvailable": telemetry_available_for_pool,
            "telemetryUrl": telemetry_url,
            "workers": worker_items,
        })

    return result
