"""PostgreSQL repository for globally unique Nexus pool instances."""

from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from backend.db.connection import get_connection, transaction


def upsert_pool(pool: dict[str, Any]) -> dict[str, Any]:
    pool_id = str(pool.get("poolId") or pool.get("id") or "").strip()
    if not pool_id:
        raise ValueError("Pool requires poolId or id.")

    values = {
        "pool_id": pool_id,
        "asset_id": pool.get("assetId") or None,
        "name": str(pool.get("name") or pool_id),
        "coin": str(pool.get("coin") or "UNKNOWN").upper(),
        "mode": str(pool.get("mode") or "solo"),
        "visibility": str(pool.get("visibility") or ("public" if pool.get("mode") == "public" else "private")),
        "status": str(pool.get("status") or "unknown"),
        "native_pool_id": str(pool.get("nativePoolId") or pool.get("native_pool_id") or pool.get("poolId") or ""),
        "instance_name": str(pool.get("instanceName") or pool.get("instance_name") or ""),
        "host": str(pool.get("host") or pool.get("poolHost") or ""),
        "api_port": pool.get("apiPort") or pool.get("api_port"),
        "api_base": str(pool.get("apiBase") or pool.get("api_base") or ""),
        "stratum_ports": Jsonb(pool.get("stratumPorts") or pool.get("stratum_ports") or []),
        "instance_id": pool.get("instanceId") or None,
        "configuration": Jsonb(pool.get("configuration") or {}),
        "observed_state": Jsonb(pool.get("observedState") or {}),
        "metadata": Jsonb(pool.get("metadata") or {}),
    }

    with transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO nexus.pools (
                    pool_id, asset_id, name, coin, mode, visibility, status,
                    native_pool_id, instance_name, host, api_port, api_base,
                    stratum_ports, instance_id, configuration, observed_state,
                    metadata, created_at, updated_at, last_seen_at
                )
                VALUES (
                    %(pool_id)s, %(asset_id)s, %(name)s, %(coin)s, %(mode)s,
                    %(visibility)s, %(status)s, %(native_pool_id)s,
                    %(instance_name)s, %(host)s, %(api_port)s, %(api_base)s,
                    %(stratum_ports)s, %(instance_id)s, %(configuration)s,
                    %(observed_state)s, %(metadata)s, NOW(), NOW(), NOW()
                )
                ON CONFLICT (pool_id) DO UPDATE SET
                    asset_id = EXCLUDED.asset_id,
                    name = EXCLUDED.name,
                    coin = EXCLUDED.coin,
                    mode = EXCLUDED.mode,
                    visibility = EXCLUDED.visibility,
                    status = EXCLUDED.status,
                    native_pool_id = EXCLUDED.native_pool_id,
                    instance_name = EXCLUDED.instance_name,
                    host = EXCLUDED.host,
                    api_port = EXCLUDED.api_port,
                    api_base = EXCLUDED.api_base,
                    stratum_ports = EXCLUDED.stratum_ports,
                    instance_id = EXCLUDED.instance_id,
                    configuration = EXCLUDED.configuration,
                    observed_state = EXCLUDED.observed_state,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW(),
                    last_seen_at = NOW()
                RETURNING *
                """,
                values,
            )
            return dict(cursor.fetchone() or {})


def list_pools() -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM nexus.pools
                ORDER BY coin, name, pool_id
                """
            )
            rows = cursor.fetchall()

    return [
        {
            "poolId": row["pool_id"],
            "assetId": row["asset_id"],
            "name": row["name"],
            "coin": row["coin"],
            "mode": row["mode"],
            "visibility": row["visibility"],
            "status": row["status"],
            "nativePoolId": row["native_pool_id"],
            "instanceName": row["instance_name"],
            "host": row["host"],
            "apiPort": row["api_port"],
            "apiBase": row["api_base"],
            "stratumPorts": row["stratum_ports"] or [],
            "instanceId": row["instance_id"],
            "configuration": row["configuration"] or {},
            "observedState": row["observed_state"] or {},
            "metadata": row["metadata"] or {},
            "lastSeenAt": row["last_seen_at"].isoformat() if row["last_seen_at"] else None,
        }
        for row in rows
    ]


def get_pool(pool_id: str) -> dict[str, Any] | None:
    return next((pool for pool in list_pools() if pool["poolId"] == pool_id), None)
