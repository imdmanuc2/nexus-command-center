"""Canonical operational state reconciliation for Nexus CMDB objects."""
from __future__ import annotations

from typing import Any

from backend.db.connection import transaction
from backend.db.repositories.asset_repository import list_assets
from backend.db.repositories.blockchain_repository import list_blockchain_nodes
from backend.db.repositories.pool_repository import list_pools
from backend.db.repositories.worker_repository import list_active_workers



def derive_pool_operational_state(
    pool: dict[str, Any],
    active_workers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return the canonical live operational state for one mining pool.

    Pool inventory status describes reachability/lifecycle. Operator-facing
    state is derived from live telemetry and current worker ownership.
    """
    observed = pool.get("observedState") or {}
    pool_id = str(pool.get("poolId") or "").strip()
    workers = active_workers or []
    matched_workers = [
        worker for worker in workers
        if str(worker.get("poolInstanceId") or "").strip() == pool_id
        and worker.get("currentSession") is True
        and str(worker.get("status") or "").lower() not in {
            "offline", "stale", "retired", "disconnected"
        }
        and str(worker.get("activityState") or "").lower() not in {
            "offline", "stale", "retired", "disconnected"
        }
    ]

    worker_count = max(
        len(matched_workers),
        int(pool.get("onlineWorkerCount") or observed.get("activeWorkers") or 0),
    )
    worker_hashrate = sum(float(worker.get("currentHashrate") or 0) for worker in matched_workers)
    hashrate = max(
        worker_hashrate,
        float(pool.get("currentHashrate") or observed.get("hashrate") or 0),
    )

    api_reachable = observed.get("apiReachable")
    stratum_reachable = observed.get("stratumReachable")
    raw_status = str(pool.get("status") or "").lower()

    if raw_status in {"offline", "down", "error"} or api_reachable is False or stratum_reachable is False:
        state = "offline"
    elif worker_count > 0 and hashrate > 0:
        state = "accepting-shares"
    elif worker_count > 0:
        state = "hashrate-stabilizing"
    elif raw_status in {"degraded", "warning"}:
        state = "degraded"
    else:
        state = "online"

    return {
        "poolId": pool_id,
        "observedOperationalState": state,
        "hashrate": hashrate,
        "activeWorkers": worker_count,
    }

def reconcile_operational_state() -> dict[str, Any]:
    """Project current observations into canonical CMDB object state.

    Collectors own facts. This engine owns the operator-facing observed state.
    """
    assets = list_assets()
    workers = list_active_workers()
    pools = list_pools()
    blockchain_nodes = list_blockchain_nodes()

    active_by_asset: dict[str, dict[str, Any]] = {}
    for worker in workers:
        asset_id = str(worker.get("assetId") or "").strip()
        if not asset_id:
            continue
        current = active_by_asset.get(asset_id)
        if current is None or float(worker.get("currentHashrate") or 0) > float(current.get("currentHashrate") or 0):
            active_by_asset[asset_id] = worker

    node_by_asset = {
        str(node.get("assetId") or node.get("nodeId") or ""): node
        for node in blockchain_nodes
        if node.get("assetId") or node.get("nodeId")
    }

    asset_updates = 0
    with transaction() as connection:
        with connection.cursor() as cursor:
            for asset in assets:
                asset_id = str(asset.get("id") or asset.get("assetId") or "").strip()
                if not asset_id:
                    continue
                asset_type = str(asset.get("assetType") or asset.get("type") or "").lower()
                worker = active_by_asset.get(asset_id)
                node = node_by_asset.get(asset_id)

                if worker:
                    phase = str((worker.get("observedState") or {}).get("phase") or "").lower()
                    hashrate = float(worker.get("currentHashrate") or 0)
                    observed = "hashrate-stabilizing" if phase == "hashrate-stabilizing" and hashrate <= 0 else "mining"
                    health = "healthy" if str(worker.get("status") or "").lower() == "online" else "warning"
                    connectivity = "connected" if worker.get("connectionConfirmed") or worker.get("telemetryAvailable") else "intermittent"
                elif node:
                    sync = float(node.get("syncPercent") or 0)
                    rpc = bool(node.get("rpcConnected"))
                    observed = "synchronized" if sync >= 99.99 and rpc else "synchronizing" if rpc else "offline"
                    health = "healthy" if observed == "synchronized" else "warning" if rpc else "critical"
                    connectivity = "connected" if rpc else "disconnected"
                elif asset_type in {"asic", "miner", "mining-worker"}:
                    observed, health, connectivity = "idle", "unknown", "unknown"
                else:
                    continue

                cursor.execute(
                    """
                    UPDATE nexus.assets
                    SET observed_operational_mode = %s,
                        health_state = %s,
                        connectivity_state = %s,
                        updated_at = NOW()
                    WHERE asset_id = %s
                    """,
                    (observed, health, connectivity, asset_id),
                )
                asset_updates += cursor.rowcount

    pool_states = [
        derive_pool_operational_state(pool, workers)
        for pool in pools
    ]

    return {
        "status": "ok",
        "source": "nexus-operational-state-engine",
        "assetsUpdated": asset_updates,
        "activeMiningAssets": len(active_by_asset),
        "poolsEvaluated": len(pool_states),
        "poolStates": pool_states,
    }
