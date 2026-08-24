from __future__ import annotations

from typing import Any

from backend.db.connection import get_connection
from backend.services.blockchain_runtime_health_service import (
    derive_blockchain_runtime_health,
)


def _rows(cursor) -> list[dict[str, Any]]:
    return [dict(row) for row in cursor.fetchall()]


def get_blockchain_operations() -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    n.node_id,
                    n.asset_id,
                    n.coin,
                    n.network,
                    n.implementation,
                    n.version,
                    n.status,
                    n.sync_status,
                    n.block_height,
                    n.header_height,
                    n.peer_count,
                    n.rpc_connected,
                    n.observed_state,
                    n.updated_at,
                    n.last_seen_at,
                    a.name,
                    n.ip_address,
                    a.lifecycle_status,
                    a.health_state AS health,
                    a.connectivity_state AS connectivity
                FROM nexus.blockchain_nodes n
                LEFT JOIN nexus.assets a
                  ON a.asset_id = n.asset_id
                ORDER BY n.coin, n.asset_id
                """
            )
            nodes = _rows(cur)

            asset_ids = [
                row["asset_id"]
                for row in nodes
                if row.get("asset_id")
            ]

            metrics_by_asset: dict[str, dict[str, dict[str, Any]]] = {}

            if asset_ids:
                cur.execute(
                    """
                    SELECT
                        subject_id,
                        metric_name,
                        metric_value,
                        metric_unit,
                        status,
                        observed_at
                    FROM nexus.current_metrics
                    WHERE subject_id = ANY(%s)
                    ORDER BY subject_id, metric_name
                    """,
                    (asset_ids,),
                )

                for row in _rows(cur):
                    metrics_by_asset.setdefault(
                        row["subject_id"],
                        {},
                    )[row["metric_name"]] = row

            manager_by_runtime: dict[str, dict[str, Any]] = {}

            if asset_ids:
                cur.execute(
                    """
                    SELECT
                        r.source_id AS manager_asset_id,
                        r.target_id AS runtime_asset_id,
                        r.status,
                        r.last_seen_at,
                        a.name AS manager_name
                    FROM nexus.relationships r
                    LEFT JOIN nexus.assets a
                      ON a.asset_id = r.source_id
                    WHERE r.relationship_type = 'manages'
                      AND r.target_id = ANY(%s)
                      AND r.status = 'active'
                    ORDER BY r.last_seen_at DESC NULLS LAST
                    """,
                    (asset_ids,),
                )

                for row in _rows(cur):
                    manager_by_runtime.setdefault(
                        row["runtime_asset_id"],
                        row,
                    )

    items: list[dict[str, Any]] = []

    for node in nodes:
        asset_id = node["asset_id"]
        metrics = metrics_by_asset.get(asset_id, {})

        def metric(name: str):
            value = metrics.get(name)
            return value.get("metric_value") if value else None

        sync_progress = metric("sync_progress")

        rpc_reachable = metric("runtime.rpc.reachable")
        if rpc_reachable is None:
            rpc_reachable = metric("rpc_reachable")

        rpc_healthy = metric("runtime.rpc.healthy")
        running = metric("running")
        ibd = metric("runtime.initial_block_download")

        if ibd is None:
            ibd = metric("initial_block_download")

        sync_status = str(
            node.get("sync_status") or ""
        ).strip().lower()

        node_status = str(
            node.get("status") or ""
        ).strip().lower()

        # Canonical provider-neutral operational-state precedence.
        #
        # New Seymour-managed runtimes expose lifecycle state through
        # current_metrics. Older/native blockchain discovery may instead
        # expose node status and rpc_connected directly on blockchain_nodes.
        #
        # Do not allow placeholder values such as "unknown" to mask useful
        # lower-level evidence.
        if running == 0:
            state = "stopped"
        elif ibd == 1 and rpc_reachable == 1:
            state = "syncing"
        elif running == 1 and rpc_healthy == 1:
            state = "running"
        elif running == 1:
            state = "running"
        elif sync_status and sync_status != "unknown":
            state = sync_status
        elif node_status and node_status != "unknown":
            state = node_status
        elif node.get("rpc_connected") is True:
            state = "online"
        else:
            state = "unknown"

        manager = manager_by_runtime.get(asset_id)

        # blockchain_nodes.rpc_connected is authoritative for native /
        # independently discovered blockchain nodes. Seymour-managed
        # runtimes must use explicit runtime RPC telemetry instead.
        #
        # Registration may create a blockchain_nodes row with
        # rpc_connected=false even when no RPC observation has occurred.
        # Treating that default as telemetry incorrectly marks a running
        # managed runtime unreachable.
        native_rpc_connected = (
            node.get("rpc_connected")
            if manager is None
            else None
        )

        # blockchain_nodes.status follows the same authority rule.
        # For independently discovered nodes it represents an actual
        # operational observation. For Seymour-managed runtimes the row
        # may contain a registration fallback such as "offline" even
        # though no runtime connectivity observation has occurred.
        authoritative_node_status = (
            node.get("status")
            if manager is None
            else None
        )

        canonical_health = (
            derive_blockchain_runtime_health(
                {
                    "running": (
                        None
                        if running is None
                        else bool(running)
                    ),
                    "nodeStatus": authoritative_node_status,
                    "lifecycleStatus": node.get(
                        "lifecycle_status"
                    ),
                    "syncStatus": node.get(
                        "sync_status"
                    ),
                    "syncProgress": sync_progress,
                    "blockHeight": node.get(
                        "block_height"
                    ),
                    "headerHeight": node.get(
                        "header_height"
                    ),
                    "initialBlockDownload": (
                        None
                        if ibd is None
                        else bool(ibd)
                    ),
                    "rpcReachable": (
                        None
                        if rpc_reachable is None
                        else bool(rpc_reachable)
                    ),
                    "rpcHealthy": (
                        None
                        if rpc_healthy is None
                        else bool(rpc_healthy)
                    ),
                    "rpcConnected": native_rpc_connected,
                }
            )
        )

        items.append(
            {
                "nodeId": node.get("node_id"),
                "assetId": asset_id,
                "name": (
                    node.get("name")
                    or node.get("implementation")
                    or asset_id
                ),
                "coin": node.get("coin"),
                "network": node.get("network"),
                "implementation": node.get("implementation"),
                "version": node.get("version"),
                "state": state,
                "nodeStatus": node.get("status"),
                "syncStatus": node.get("sync_status"),
                "syncProgress": sync_progress,
                "blockHeight": node.get("block_height"),
                "headerHeight": node.get("header_height"),
                "peerCount": node.get("peer_count"),
                "rpcReachable": (
                    None
                    if rpc_reachable is None
                    else bool(rpc_reachable)
                ),
                "rpcHealthy": (
                    None
                    if rpc_healthy is None
                    else bool(rpc_healthy)
                ),
                "running": (
                    None
                    if running is None
                    else bool(running)
                ),
                "initialBlockDownload": (
                    None
                    if ibd is None
                    else bool(ibd)
                ),
                "ipAddress": node.get("ip_address"),
                "lifecycleStatus": node.get("lifecycle_status"),
                "health": node.get("health"),
                "connectivity": node.get("connectivity"),
                "manager": manager,

                # Canonical blockchain health dimensions.
                "runtimeState": canonical_health[
                    "runtimeState"
                ],
                "connectivityState": canonical_health[
                    "connectivityState"
                ],
                "syncState": canonical_health[
                    "syncState"
                ],
                "rpcState": canonical_health[
                    "rpcState"
                ],
                "miningReadiness": canonical_health[
                    "miningReadiness"
                ],
                "overallState": canonical_health[
                    "overallState"
                ],
                "stateReason": canonical_health[
                    "stateReason"
                ],

                "lastSeenAt": node.get("last_seen_at"),
                "updatedAt": node.get("updated_at"),
            }
        )

    return {
        "status": "ok",
        "source": "nexus-postgresql-platform",
        "count": len(items),
        "syncing": sum(
            1 for item in items
            if item["overallState"] == "syncing"
        ),
        "running": sum(
            1 for item in items
            if item["overallState"] in {
                "running",
                "ready",
            }
        ),
        "warning": sum(
            1 for item in items
            if item["overallState"] in {
                "warning",
                "degraded",
                "stalled",
            }
        ),
        "offline": sum(
            1 for item in items
            if item["overallState"] in {
                "offline",
                "stopped",
                "error",
            }
        ),
        "items": items,
    }
