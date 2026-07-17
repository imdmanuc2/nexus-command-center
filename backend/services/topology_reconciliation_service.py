
from __future__ import annotations

from typing import Any

from backend.db.repositories.blockchain_repository import (
    list_blockchain_nodes,
)
from backend.db.repositories.pool_repository import list_pools
from backend.db.repositories.relationship_repository import (
    reconcile_topology_relationships,
)
from backend.db.repositories.topology_repository import (
    update_topology_reconciliation_state,
)
from backend.db.repositories.worker_repository import (
    list_active_workers,
)


def _relationship_id(
    source_type: str,
    source_id: str,
    relationship_type: str,
    target_type: str,
    target_id: str,
) -> str:
    clean = (
        f"{source_type}-{source_id}-"
        f"{relationship_type}-{target_type}-{target_id}"
    )
    return "topology-" + "".join(
        character if character.isalnum() else "-"
        for character in clean.lower()
    )


def reconcile_live_topology() -> dict[str, Any]:
    workers = list_active_workers()
    pools = list_pools()
    nodes = list_blockchain_nodes()

    pool_ids = {
        str(pool.get("poolId"))
        for pool in pools
        if pool.get("poolId")
    }

    relationships: list[dict[str, Any]] = []

    for worker in workers:
        pool_id = str(
            worker.get("poolInstanceId")
            or ""
        ).strip()

        if not pool_id or pool_id not in pool_ids:
            continue

        asset_id = str(worker.get("assetId") or "").strip()

        source_type = "asset" if asset_id else "worker"
        source_id = asset_id or str(worker.get("workerId"))

        relationships.append({
            "relationshipId": _relationship_id(
                source_type,
                source_id,
                "mines-on",
                "pool",
                pool_id,
            ),
            "sourceType": source_type,
            "sourceId": source_id,
            "relationshipType": "mines-on",
            "targetType": "pool",
            "targetId": pool_id,
            "confidence": 100,
            "metadata": {
                "canonicalWorkerId": worker.get("workerId"),
                "sourceWorkerId": worker.get("sourceWorkerId"),
                "activityState": worker.get("activityState"),
                "currentSession": worker.get("currentSession"),
                "currentHashrate": worker.get("currentHashrate") or 0,
                "sharesPerSecond": worker.get("sharesPerSecond") or 0,
                "sourceSystem": worker.get("sourceSystem"),
            },
        })

    healthy_nodes = [
        node
        for node in nodes
        if str(node.get("status") or "").lower()
        not in {"offline", "down", "error", "stale"}
    ]

    for pool in pools:
        pool_id = str(pool.get("poolId") or "").strip()
        coin = str(pool.get("coin") or "").upper().strip()

        if not pool_id or not coin:
            continue

        matches = [
            node
            for node in healthy_nodes
            if str(node.get("coin") or "").upper().strip() == coin
        ]

        if not matches:
            continue

        # Prefer RPC-connected and most recently observed nodes.
        node = max(
            matches,
            key=lambda item: (
                bool(item.get("rpcConnected")),
                str(item.get("lastSeenAt") or ""),
            ),
        )

        target_id = str(
            node.get("assetId")
            or node.get("nodeId")
        )

        relationships.append({
            "relationshipId": _relationship_id(
                "pool",
                pool_id,
                "backed-by",
                "asset",
                target_id,
            ),
            "sourceType": "pool",
            "sourceId": pool_id,
            "relationshipType": "backed-by",
            "targetType": "asset",
            "targetId": target_id,
            "confidence": 100,
            "metadata": {
                "coin": coin,
                "blockchainNodeId": node.get("nodeId"),
                "rpcConnected": node.get("rpcConnected"),
                "syncPercent": node.get("syncPercent"),
            },
        })

    result = reconcile_topology_relationships(relationships)

    update_topology_reconciliation_state(
        status="ok",
        written=result["written"],
        deactivated=result["deactivated"],
    )

    return {
        "status": "ok",
        "source": "nexus-live-postgresql-topology",
        "workersEvaluated": len(workers),
        "poolsEvaluated": len(pools),
        "blockchainNodesEvaluated": len(nodes),
        "relationshipsWritten": result["written"],
        "relationshipsDeactivated": result["deactivated"],
    }
