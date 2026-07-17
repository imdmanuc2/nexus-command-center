"""PostgreSQL repository for persisted blockchain nodes."""

from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from backend.db.connection import get_connection, transaction


def upsert_blockchain_node(node: dict[str, Any]) -> dict[str, Any]:
    """Insert or update a blockchain node using its stable node identity."""

    asset_id = str(
        node.get("asset_id")
        or node.get("node_id")
        or ""
    ).strip()

    node_id = str(
        node.get("node_id")
        or asset_id
    ).strip()

    if not asset_id:
        raise ValueError("Blockchain node asset_id is required.")

    if not node_id:
        raise ValueError("Blockchain node node_id is required.")

    params = {
        **node,
        "asset_id": asset_id,
        "node_id": node_id,
        "raw_payload": Jsonb(node.get("raw_payload") or {}),
    }

    with transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO nexus.blockchain_nodes (
                    asset_id,
                    node_id,
                    name,
                    coin,
                    chain,
                    host,
                    ip_address,
                    rpc_port,
                    p2p_port,
                    rpc_connected,
                    status,
                    version,
                    block_height,
                    header_height,
                    sync_percent,
                    peer_count,
                    mempool_transactions,
                    disk_usage_bytes,
                    first_seen_at,
                    last_seen_at,
                    last_changed_at,
                    raw_payload,
                    updated_at
                )
                VALUES (
                    %(asset_id)s,
                    %(node_id)s,
                    %(name)s,
                    %(coin)s,
                    %(chain)s,
                    %(host)s,
                    %(ip_address)s,
                    %(rpc_port)s,
                    %(p2p_port)s,
                    %(rpc_connected)s,
                    %(status)s,
                    %(version)s,
                    %(block_height)s,
                    %(header_height)s,
                    %(sync_percent)s,
                    %(peer_count)s,
                    %(mempool_transactions)s,
                    %(disk_usage_bytes)s,
                    NOW(),
                    NOW(),
                    NOW(),
                    %(raw_payload)s,
                    NOW()
                )
                ON CONFLICT (node_id)
                DO UPDATE SET
                    asset_id = EXCLUDED.asset_id,
                    name = EXCLUDED.name,
                    coin = EXCLUDED.coin,
                    chain = EXCLUDED.chain,
                    host = EXCLUDED.host,
                    ip_address = EXCLUDED.ip_address,
                    rpc_port = EXCLUDED.rpc_port,
                    p2p_port = EXCLUDED.p2p_port,
                    rpc_connected = EXCLUDED.rpc_connected,
                    status = EXCLUDED.status,
                    version = EXCLUDED.version,
                    block_height = EXCLUDED.block_height,
                    header_height = EXCLUDED.header_height,
                    sync_percent = EXCLUDED.sync_percent,
                    peer_count = EXCLUDED.peer_count,
                    mempool_transactions = EXCLUDED.mempool_transactions,
                    disk_usage_bytes = EXCLUDED.disk_usage_bytes,
                    last_seen_at = NOW(),
                    last_changed_at = CASE
                        WHEN (
                            nexus.blockchain_nodes.rpc_connected,
                            nexus.blockchain_nodes.status,
                            nexus.blockchain_nodes.version,
                            nexus.blockchain_nodes.block_height,
                            nexus.blockchain_nodes.header_height,
                            nexus.blockchain_nodes.sync_percent,
                            nexus.blockchain_nodes.peer_count
                        ) IS DISTINCT FROM (
                            EXCLUDED.rpc_connected,
                            EXCLUDED.status,
                            EXCLUDED.version,
                            EXCLUDED.block_height,
                            EXCLUDED.header_height,
                            EXCLUDED.sync_percent,
                            EXCLUDED.peer_count
                        )
                        THEN NOW()
                        ELSE nexus.blockchain_nodes.last_changed_at
                    END,
                    raw_payload = EXCLUDED.raw_payload,
                    updated_at = NOW()
                RETURNING *
                """,
                params,
            )

            row = cursor.fetchone()

    return _serialize(row)


def list_blockchain_nodes() -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM nexus.blockchain_nodes
                ORDER BY name, node_id
                """
            )
            rows = cursor.fetchall()

    return [_serialize(row) for row in rows]


def mark_stale_blockchain_nodes(
    stale_seconds: int = 300,
) -> int:
    with transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE nexus.blockchain_nodes
                SET
                    rpc_connected = FALSE,
                    status = 'offline',
                    updated_at = NOW()
                WHERE last_seen_at
                      < NOW() - (%s * INTERVAL '1 second')
                  AND status <> 'offline'
                """,
                (stale_seconds,),
            )

            return cursor.rowcount


def _serialize(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "assetId": row["asset_id"],
        "nodeId": row["node_id"],
        "name": row["name"],
        "coin": row["coin"],
        "chain": row["chain"],
        "host": row["host"],
        "ip": row["ip_address"],
        "rpcPort": row["rpc_port"],
        "p2pPort": row["p2p_port"],
        "rpcConnected": row["rpc_connected"],
        "status": row["status"],
        "version": row["version"],
        "blockHeight": row["block_height"],
        "headers": row["header_height"],
        "syncPercent": row["sync_percent"],
        "peers": row["peer_count"],
        "mempoolTransactions": row["mempool_transactions"],
        "diskUsageBytes": row["disk_usage_bytes"],
        "firstSeenAt": (
            row["first_seen_at"].isoformat()
            if row["first_seen_at"]
            else None
        ),
        "lastSeenAt": (
            row["last_seen_at"].isoformat()
            if row["last_seen_at"]
            else None
        ),
        "lastChangedAt": (
            row["last_changed_at"].isoformat()
            if row["last_changed_at"]
            else None
        ),
        "updatedAt": (
            row["updated_at"].isoformat()
            if row["updated_at"]
            else None
        ),
        "raw": row["raw_payload"] or {},
    }
