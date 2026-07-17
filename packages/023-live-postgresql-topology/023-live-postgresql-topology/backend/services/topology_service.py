
from __future__ import annotations

from typing import Any

from backend.db.repositories.asset_repository import list_assets
from backend.db.repositories.blockchain_repository import (
    list_blockchain_nodes,
)
from backend.db.repositories.pool_repository import list_pools
from backend.db.repositories.relationship_repository import (
    list_active_relationships,
)
from backend.db.repositories.worker_repository import (
    list_active_workers,
)
from backend.db.repositories.workload_repository import list_workloads


def _asset_status(asset: dict[str, Any]) -> str:
    observed = asset.get("observedState") or {}
    return str(
        observed.get("status")
        or asset.get("lifecycleStatus")
        or "unknown"
    )


def topology() -> dict[str, Any]:
    assets = list_assets()
    pools = list_pools()
    workers = list_active_workers()
    workloads = list_workloads()
    blockchain_nodes = list_blockchain_nodes()
    relationships = list_active_relationships()

    active_worker_ids = {
        worker["workerId"]
        for worker in workers
    }

    active_asset_ids = {
        worker["assetId"]
        for worker in workers
        if worker.get("assetId")
    }

    asset_map = {
        asset["id"]: {
            "id": asset["id"],
            "nodeType": "asset",
            "assetType": asset.get("assetType"),
            "label": (
                asset.get("friendlyName")
                or asset.get("displayName")
                or asset.get("name")
                or asset["id"]
            ),
            "status": _asset_status(asset),
            "properties": dict(asset),
        }
        for asset in assets
    }

    # Fold persisted blockchain state into its physical asset node.
    for node in blockchain_nodes:
        asset_id = str(
            node.get("assetId")
            or node.get("nodeId")
        )

        properties = {
            **(asset_map.get(asset_id, {}).get("properties") or {}),
            **node,
            "assetType": "blockchain-node",
            "blockchainNode": True,
        }

        asset_map[asset_id] = {
            "id": asset_id,
            "nodeType": "asset",
            "assetType": "blockchain-node",
            "label": (
                node.get("name")
                or asset_map.get(asset_id, {}).get("label")
                or asset_id
            ),
            "status": node.get("status") or "unknown",
            "properties": properties,
        }

    # Attach current worker state directly to its physical asset.
    for worker in workers:
        asset_id = worker.get("assetId")
        if not asset_id or asset_id not in asset_map:
            continue

        node = asset_map[asset_id]
        node["status"] = (
            "mining"
            if float(worker.get("currentHashrate") or 0) > 0
            else worker.get("status")
            or worker.get("activityState")
            or node["status"]
        )
        node["properties"].update({
            "liveWorkerId": worker.get("sourceWorkerId"),
            "canonicalWorkerId": worker.get("workerId"),
            "liveHashrate": worker.get("currentHashrate") or 0,
            "liveSharesPerSecond": worker.get("sharesPerSecond") or 0,
            "livePoolId": worker.get("poolInstanceId") or "",
            "livePoolHost": worker.get("poolHost") or "",
            "activityState": worker.get("activityState"),
            "connectionConfirmed": worker.get("connectionConfirmed"),
            "telemetryAvailable": worker.get("telemetryAvailable"),
            "currentSession": worker.get("currentSession"),
        })

    nodes = list(asset_map.values())

    for pool in pools:
        nodes.append({
            "id": pool["poolId"],
            "nodeType": "pool",
            "assetType": "pool",
            "label": pool.get("name") or pool["poolId"],
            "status": pool.get("status") or "unknown",
            "properties": {
                **pool,
                "assetType": "pool",
            },
        })

    # Only unbound active workers need standalone topology nodes.
    for worker in workers:
        if worker.get("assetId"):
            continue

        nodes.append({
            "id": worker["workerId"],
            "nodeType": "worker",
            "assetType": worker.get("workerType") or "worker",
            "label": worker.get("displayName") or worker["workerId"],
            "status": worker.get("status") or worker.get("activityState"),
            "properties": worker,
        })

    # Workloads are retained for Engineering mode only and limited to current workers.
    for workload in workloads:
        worker_id = workload.get("workerId")
        if worker_id and worker_id not in active_worker_ids:
            continue

        nodes.append({
            "id": workload["workloadId"],
            "nodeType": "workload",
            "assetType": workload.get("workloadType") or "workload",
            "label": workload.get("name") or workload["workloadId"],
            "status": workload.get("status") or "unknown",
            "properties": workload,
        })

    node_ids = {node["id"] for node in nodes}
    edge_keys: set[tuple[str, str, str]] = set()
    edges = []

    for relationship in relationships:
        source_id = relationship["sourceId"]
        target_id = relationship["targetId"]
        relationship_type = relationship["relationshipType"]

        if source_id not in node_ids or target_id not in node_ids:
            continue

        key = (source_id, target_id, relationship_type)
        if key in edge_keys:
            continue

        edge_keys.add(key)
        edges.append({
            "id": relationship["relationshipId"],
            "source": source_id,
            "target": target_id,
            "type": relationship_type,
            "status": relationship.get("status") or "active",
            "confidence": relationship.get("confidence"),
            "properties": {
                **(relationship.get("metadata") or {}),
                "relationshipSource": relationship.get("source"),
            },
        })

    return {
        "status": "ok",
        "source": "nexus-postgresql-live-topology",
        "counts": {
            "nodes": len(nodes),
            "edges": len(edges),
            "assets": len(asset_map),
            "workers": len(workers),
            "workerNodes": sum(
                1
                for node in nodes
                if node["nodeType"] == "worker"
            ),
            "activePhysicalAssets": len(active_asset_ids),
            "pools": len(pools),
            "blockchainNodes": len(blockchain_nodes),
            "workloads": sum(
                1
                for node in nodes
                if node["nodeType"] == "workload"
            ),
        },
        "nodes": nodes,
        "edges": edges,
    }
