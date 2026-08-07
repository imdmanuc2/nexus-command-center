"""Normalize Seymour Pool Engine live telemetry into the Nexus CMDB.

Nexus owns inventory, lifecycle and relationships. Seymour owns native
Stratum sessions, shares, jobs, VarDiff and live mining telemetry.
"""
from __future__ import annotations

import json
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from backend.db.repositories.asset_repository import list_assets
from backend.db.repositories.pool_repository import upsert_pool
from backend.db.repositories.worker_repository import upsert_worker
from backend.db.repositories.workload_repository import upsert_workload
from backend.db.repositories.relationship_repository import upsert_relationship
from backend.services.worker_identity_classification_service import (
    asset_display_name, build_asset_indexes, classify_worker, resolve_worker_asset,
)

CONFIG_PATH = Path("backend/data/config/seymour_pool_engine.json")
SHARE_ACTIVE_PHASES = {"submitting-shares", "hashrate-stabilizing", "stable"}
CURRENT_SESSION_PHASES = {
    "connected", "authorized", "receiving-jobs",
    "submitting-shares", "hashrate-stabilizing", "stable",
}


def _fetch_json(url: str, timeout: float = 5.0) -> Any:
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _reachable(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except (OSError, ValueError):
        return False


def _load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {"enabled": False}
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {"enabled": False}


def _iso_recent(value: Any, max_age_seconds: int) -> bool:
    if not value:
        return False
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()
        return 0 <= age <= max_age_seconds
    except (TypeError, ValueError):
        return False


def _asset_identity_indexes() -> tuple[dict[str, str], dict[str, str]]:
    """Build stable CMDB identity indexes for live worker reconciliation.

    Miner IPs may change and older CMDB records can retain historical IPs.
    The configured worker suffix is therefore the preferred stable identity,
    with remote IP used as supporting evidence.
    """
    by_ip: dict[str, str] = {}
    by_suffix: dict[str, str] = {}
    for asset in list_assets():
        asset_id = str(asset.get("id") or asset.get("assetId") or "").strip()
        if not asset_id:
            continue
        candidates = [
            asset.get("ip"),
            (asset.get("observedState") or {}).get("ip"),
            ((asset.get("metadata") or {}).get("legacy") or {}).get("ip"),
        ]
        for candidate in candidates:
            value = str(candidate or "").strip()
            if value:
                by_ip[value] = asset_id

        worker_suffix = str(asset.get("workerId") or "").strip().lower()
        if worker_suffix:
            by_suffix[worker_suffix] = asset_id
    return by_ip, by_suffix


def _relationship(source_type: str, source_id: str, rel_type: str,
                  target_type: str, target_id: str, metadata: dict[str, Any]) -> None:
    safe = "-".join(
        str(part).lower().replace("_", "-").replace(" ", "-")
        for part in (source_type, source_id, rel_type, target_type, target_id)
    )
    upsert_relationship({
        "relationshipId": f"seymour-{safe}",
        "sourceType": source_type,
        "sourceId": source_id,
        "relationshipType": rel_type,
        "targetType": target_type,
        "targetId": target_id,
        "status": "active",
        "confidence": 100,
        "source": "seymour-native-stratum",
        "observed": True,
        "approved": True,
        "metadata": metadata,
    })


def synchronize_seymour_pool_engine() -> dict[str, Any]:
    config = _load_config()
    if not config.get("enabled", True):
        return {"status": "disabled", "source": "seymour-native-stratum"}

    host = str(config.get("host") or "192.168.1.169")
    api_port = int(config.get("apiPort") or 8561)
    stratum_port = int(config.get("stratumPort") or 3336)
    pool_id = str(config.get("poolId") or "seymour-btc-solo")
    native_pool_id = str(config.get("nativePoolId") or "btc-solo")
    blockchain_asset_id = str(config.get("blockchainAssetId") or "asset-82ac3c36")
    base = f"http://{host}:{api_port}"
    max_age = int(config.get("activeRecencySeconds") or 300)

    try:
        overview = _fetch_json(f"{base}/api/v1/statistics/overview?window=5m")
        workers_payload = _fetch_json(f"{base}/api/v1/statistics/workers?window=5m")
        engine = _fetch_json(f"{base}/api/v1/statistics/engine?window=5m")
        api_online = True
    except (OSError, URLError, ValueError, json.JSONDecodeError) as exc:
        return {
            "status": "offline",
            "source": "seymour-native-stratum",
            "error": str(exc),
            "apiReachable": False,
            "stratumReachable": _reachable(host, stratum_port),
        }

    stratum_online = _reachable(host, stratum_port)
    raw_workers = workers_payload.get("workers", workers_payload) if isinstance(workers_payload, dict) else workers_payload
    if not isinstance(raw_workers, list):
        raw_workers = []

    current_workers: list[dict[str, Any]] = []
    share_active_workers: list[dict[str, Any]] = []
    for item in raw_workers:
        if not isinstance(item, dict):
            continue
        phase = str(item.get("phase") or "").lower()
        last_activity = item.get("lastActivityAt") or item.get("lastShareAt")
        last_share = item.get("lastShareAt")
        current = bool(
            item.get("online") is True
            and phase in CURRENT_SESSION_PHASES
            and _iso_recent(last_activity, max_age)
        )
        share_active = bool(
            current
            and phase in SHARE_ACTIVE_PHASES
            and _iso_recent(last_share, max_age)
        )
        if current:
            current_workers.append(item)
        if share_active:
            share_active_workers.append(item)

    accepted = int(overview.get("acceptedShares") or 0)
    rejected = int(overview.get("rejectedShares") or 0)
    hashrate = float(overview.get("hashrate") or 0)
    last_accepted = overview.get("lastAcceptedAt")

    if not api_online or not stratum_online:
        pool_status = "offline"
    elif share_active_workers and _iso_recent(last_accepted, max_age):
        pool_status = "active"
    elif current_workers:
        pool_status = "degraded"
    else:
        pool_status = "idle"

    engine_service_id = "service-seymour-pool-engine-stratum"
    api_service_id = "service-seymour-pool-engine-api"
    host_asset_id = str(config.get("hostAssetId") or "asset-82ac3c36")

    upsert_pool({
        "poolId": pool_id,
        "nativePoolId": native_pool_id,
        "name": str(config.get("name") or "Seymour Bitcoin Solo"),
        "instanceName": "Seymour Pool Engine",
        "coin": "BTC",
        "mode": "solo",
        "visibility": "private",
        "status": pool_status,
        "host": host,
        "apiPort": api_port,
        "apiBase": base,
        "stratumPorts": [stratum_port],
        "assetId": host_asset_id,
        "configuration": {
            "implementation": "seymour-pool-engine",
            "connectorType": "native-mining-engine",
            "engineServiceId": engine_service_id,
            "apiServiceId": api_service_id,
            "blockchainAssetId": blockchain_asset_id,
            "telemetryUrl": f"{base}/api/v1/statistics/overview?window=5m",
        },
        "observedState": {
            "source": overview.get("source") or "seymour-native-stratum",
            "apiReachable": api_online,
            "stratumReachable": stratum_online,
            "activeWorkers": len(share_active_workers),
            "connectedWorkers": len(current_workers),
            "hashrate": hashrate,
            "acceptedShares": accepted,
            "rejectedShares": rejected,
            "efficiency": overview.get("efficiency"),
            "rejectionRate": overview.get("rejectionRate"),
            "lastShareAt": overview.get("lastShareAt"),
            "lastAcceptedAt": last_accepted,
            "window": overview.get("window") or "5m",
            "engine": engine if isinstance(engine, dict) else {},
        },
        "metadata": {
            "managedBy": "nexus",
            "telemetryAuthority": "seymour-pool-engine",
            "inventorySource": "seymour-native-api",
        },
    })

    assets = list_assets()
    identity_indexes = build_asset_indexes(assets)
    worker_results = []
    for item in current_workers:
        worker_name = str(item.get("workerName") or "").strip()
        if not worker_name:
            continue
        remote_host = str(item.get("remoteHost") or "").strip()
        suffix = worker_name.rsplit(".", 1)[-1] if "." in worker_name else worker_name[-3:]
        worker_id = f"worker-seymour-btc-{suffix}"
        asset, classification_source, classification_confidence = resolve_worker_asset(
            worker_name=worker_name, remote_host=remote_host,
            config=config, indexes=identity_indexes,
        )
        asset_id = str((asset or {}).get("id") or (asset or {}).get("assetId") or "") or None
        worker_type, hardware_type, role_label = classify_worker(
            worker_name=worker_name, asset=asset,
        )
        phase = str(item.get("phase") or "connected").lower()
        worker_hashrate = float(item.get("hashrate") or 0)
        has_recent_share = _iso_recent(item.get("lastShareAt"), max_age)
        share_active = phase in SHARE_ACTIVE_PHASES and has_recent_share
        activity_state = "active" if share_active else "idle"
        worker_status = "online"
        fallback_name = "Nano 3s" if suffix == "001" else "Mining System 2" if suffix == "002" else worker_name
        display_name = asset_display_name(asset, str(item.get("displayName") or fallback_name))

        upsert_worker({
            "workerId": worker_id,
            "sourceSystem": "seymour-native-stratum",
            "sourceWorkerId": worker_name,
            "workerType": worker_type,
            "hardwareType": hardware_type,
            "displayName": display_name,
            "assetId": asset_id,
            "assetMatched": bool(asset_id),
            "reconciliationStatus": "matched" if asset_id else "unmatched",
            "classificationSource": classification_source,
            "classificationConfidence": classification_confidence,
            "poolId": native_pool_id,
            "nativePoolId": native_pool_id,
            "poolInstanceId": pool_id,
            "poolHost": host,
            "poolApiPort": api_port,
            "workerName": worker_name,
            "minerAddress": worker_name.split(".", 1)[0],
            "coin": "BTC",
            "status": worker_status,
            "activityState": activity_state,
            "connectionConfirmed": True,
            "telemetryAvailable": True,
            "currentHashrate": worker_hashrate,
            "hashrateUnit": "H/s",
            "acceptedShares": item.get("acceptedShares"),
            "rejectedShares": item.get("rejectedShares"),
            "lastShareAt": item.get("lastShareAt"),
            "lastConnectedAt": item.get("connectedAt"),
            "identity": {
                "workerName": worker_name,
                "remoteHost": remote_host,
                "sessionId": item.get("sessionId"),
                "assetId": asset_id,
                "classification": worker_type,
            },
            "observedState": {
                **item,
                "activityState": activity_state,
                "currentPool": pool_id,
                "currentSession": True,
                "shareActive": share_active,
                "telemetryAuthority": "seymour-pool-engine",
            },
            "metadata": {
                "implementation": "seymour-pool-engine",
                "phase": phase,
                "remoteHost": remote_host,
                "roleLabel": role_label,
                "identityResolution": classification_source,
                "telemetryUrl": f"{base}/api/v1/statistics/workers/{worker_name}?window=5m",
            },
        })

        workload_id = f"workload-{worker_id}-btc"
        upsert_workload({
            "workloadId": workload_id,
            "assetId": asset_id,
            "workerId": worker_id,
            "workloadType": "crypto-mining",
            "name": f"{display_name} BTC Mining",
            "status": worker_status if share_active else "idle",
            "runtime": "seymour-native-stratum",
            "software": "Seymour Pool Engine",
            "coin": "BTC",
            "poolId": native_pool_id,
            "nativePoolId": native_pool_id,
            "poolInstanceId": pool_id,
            "observedState": {"hashrate": worker_hashrate, "phase": phase, "shareActive": share_active},
        })
        worker_results.append({
            "workerId": worker_id,
            "workerName": worker_name,
            "assetId": asset_id,
            "remoteHost": remote_host,
            "hashrate": worker_hashrate,
            "phase": phase,
            "activityState": activity_state,
            "shareActive": share_active,
        })

    _relationship("asset", host_asset_id, "hosts", "service", api_service_id, {"port": api_port, "unit": "seymour-pool-engine-api.service"})
    _relationship("asset", host_asset_id, "hosts", "service", engine_service_id, {"port": stratum_port, "unit": "seymour-pool-engine-stratum.service"})
    _relationship("service", engine_service_id, "serves", "pool", pool_id, {"endpoint": f"{host}:{stratum_port}"})
    _relationship("pool", pool_id, "uses-blockchain-node", "asset", blockchain_asset_id, {"coin": "BTC"})
    for worker in worker_results:
        source_type = "asset" if worker.get("assetId") else "worker"
        source_id = worker.get("assetId") or worker["workerId"]
        _relationship(source_type, source_id, "mines-on", "pool", pool_id, {
            "workerId": worker["workerId"],
            "workerName": worker["workerName"],
            "hashrate": worker["hashrate"],
            "phase": worker["phase"],
            "activityState": worker["activityState"],
            "shareActive": worker["shareActive"],
            "sourceSystem": "seymour-native-stratum",
        })

    return {
        "status": "ok",
        "source": "seymour-native-stratum",
        "poolId": pool_id,
        "poolStatus": pool_status,
        "apiReachable": api_online,
        "stratumReachable": stratum_online,
        "activeWorkers": len(worker_results),
        "hashrate": hashrate,
        "acceptedShares": accepted,
        "rejectedShares": rejected,
        "workers": worker_results,
    }
