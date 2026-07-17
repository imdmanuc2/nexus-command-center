"""PostgreSQL repository for mining and compute workloads."""

from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from backend.db.connection import get_connection, transaction


def upsert_workload(workload: dict[str, Any]) -> dict[str, Any]:
    workload_id = str(workload.get("workloadId") or workload.get("id") or "").strip()
    if not workload_id:
        raise ValueError("Workload requires workloadId or id.")

    values = {
        "workload_id": workload_id,
        "asset_id": workload.get("assetId") or None,
        "worker_id": workload.get("workerId") or None,
        "workload_type": str(workload.get("workloadType") or "unknown"),
        "name": str(workload.get("name") or workload_id),
        "status": str(workload.get("status") or "unknown"),
        "runtime": str(workload.get("runtime") or ""),
        "software": str(workload.get("software") or ""),
        "version": str(workload.get("version") or ""),
        "coin": workload.get("coin"),
        "pool_id": workload.get("nativePoolId") or workload.get("poolId") or None,
        "pool_instance_id": workload.get("poolInstanceId") or None,
        "native_pool_id": str(workload.get("nativePoolId") or workload.get("poolId") or ""),
        "allocation": Jsonb(workload.get("allocation") or {}),
        "configuration": Jsonb(workload.get("configuration") or {}),
        "observed_state": Jsonb(workload.get("observedState") or {}),
        "revenue_state": Jsonb(workload.get("revenueState") or {}),
        "metadata": Jsonb(workload.get("metadata") or {}),
    }

    with transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO nexus.workloads (
                    workload_id, asset_id, worker_id, workload_type, name,
                    status, runtime, software, version, coin, pool_id,
                    pool_instance_id, native_pool_id, allocation, configuration,
                    observed_state, revenue_state, metadata, created_at, updated_at
                )
                VALUES (
                    %(workload_id)s, %(asset_id)s, %(worker_id)s,
                    %(workload_type)s, %(name)s, %(status)s, %(runtime)s,
                    %(software)s, %(version)s, %(coin)s, %(pool_id)s,
                    %(pool_instance_id)s, %(native_pool_id)s, %(allocation)s,
                    %(configuration)s, %(observed_state)s, %(revenue_state)s,
                    %(metadata)s, NOW(), NOW()
                )
                ON CONFLICT (workload_id) DO UPDATE SET
                    asset_id = EXCLUDED.asset_id,
                    worker_id = EXCLUDED.worker_id,
                    workload_type = EXCLUDED.workload_type,
                    name = EXCLUDED.name,
                    status = EXCLUDED.status,
                    runtime = EXCLUDED.runtime,
                    software = EXCLUDED.software,
                    version = EXCLUDED.version,
                    coin = EXCLUDED.coin,
                    pool_id = EXCLUDED.pool_id,
                    pool_instance_id = EXCLUDED.pool_instance_id,
                    native_pool_id = EXCLUDED.native_pool_id,
                    allocation = EXCLUDED.allocation,
                    configuration = EXCLUDED.configuration,
                    observed_state = EXCLUDED.observed_state,
                    revenue_state = EXCLUDED.revenue_state,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
                RETURNING *
                """,
                values,
            )
            return dict(cursor.fetchone() or {})


def list_workloads() -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM nexus.workloads
                ORDER BY name, workload_id
                """
            )
            rows = cursor.fetchall()

    return [
        {
            "workloadId": row["workload_id"],
            "assetId": row["asset_id"],
            "workerId": row["worker_id"],
            "workloadType": row["workload_type"],
            "name": row["name"],
            "status": row["status"],
            "runtime": row["runtime"],
            "software": row["software"],
            "version": row["version"],
            "coin": row["coin"],
            "poolId": row["pool_id"],
            "poolInstanceId": row["pool_instance_id"],
            "nativePoolId": row["native_pool_id"],
            "allocation": row["allocation"] or {},
            "configuration": row["configuration"] or {},
            "observedState": row["observed_state"] or {},
            "revenueState": row["revenue_state"] or {},
            "metadata": row["metadata"] or {},
        }
        for row in rows
    ]
