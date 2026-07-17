"""PostgreSQL repository for live MiningCore workers."""

from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from backend.db.connection import get_connection, transaction


def upsert_worker(worker: dict[str, Any]) -> dict[str, Any]:
    worker_id = str(worker.get("workerId") or worker.get("id") or "").strip()
    if not worker_id:
        raise ValueError("Worker requires workerId or id.")

    values = {
        "worker_id": worker_id,
        "worker_type": str(worker.get("workerType") or "unknown").lower(),
        "hardware_type": str(worker.get("hardwareType") or ""),
        "display_name": str(worker.get("displayName") or worker.get("name") or worker_id),
        "asset_id": worker.get("assetId") or None,
        "asset_matched": bool(worker.get("assetMatched", bool(worker.get("assetId")))),
        "reconciliation_status": str(worker.get("reconciliationStatus") or ("matched" if worker.get("assetId") else "unmatched")),
        "pool_id": worker.get("nativePoolId") or worker.get("poolId") or None,
        "pool_instance_id": worker.get("poolInstanceId") or None,
        "native_pool_id": str(worker.get("nativePoolId") or worker.get("poolId") or ""),
        "pool_host": str(worker.get("poolHost") or ""),
        "pool_api_port": worker.get("poolApiPort"),
        "worker_name": str(worker.get("workerName") or worker.get("name") or ""),
        "miner_address": str(worker.get("minerAddress") or ""),
        "coin": worker.get("coin"),
        "status": str(worker.get("status") or "unknown"),
        "current_hashrate": worker.get("currentHashrate") or worker.get("hashrate"),
        "hashrate_unit": str(worker.get("hashrateUnit") or "H/s"),
        "shares_per_second": worker.get("sharesPerSecond"),
        "accepted_shares": worker.get("acceptedShares"),
        "rejected_shares": worker.get("rejectedShares"),
        "last_share_at": worker.get("lastShareAt"),
        "source_system": str(worker.get("sourceSystem") or "miningcore"),
        "source_worker_id": str(worker.get("sourceWorkerId") or worker_id),
        "classification_source": str(worker.get("classificationSource") or ""),
        "classification_confidence": worker.get("classificationConfidence"),
        "identity": Jsonb(worker.get("identity") or {}),
        "observed_state": Jsonb(worker.get("observedState") or {}),
        "metadata": Jsonb(worker.get("metadata") or {}),
    }

    with transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO nexus.workers (
                    worker_id, worker_type, hardware_type, display_name,
                    asset_id, asset_matched, reconciliation_status, pool_id,
                    pool_instance_id, native_pool_id, pool_host, pool_api_port,
                    worker_name, miner_address, coin, status, current_hashrate,
                    hashrate_unit, shares_per_second, accepted_shares,
                    rejected_shares, last_share_at, source_system,
                    source_worker_id, classification_source,
                    classification_confidence, identity, observed_state,
                    metadata, first_seen_at, last_seen_at, created_at, updated_at
                )
                VALUES (
                    %(worker_id)s, %(worker_type)s, %(hardware_type)s,
                    %(display_name)s, %(asset_id)s, %(asset_matched)s,
                    %(reconciliation_status)s, %(pool_id)s,
                    %(pool_instance_id)s, %(native_pool_id)s, %(pool_host)s,
                    %(pool_api_port)s, %(worker_name)s, %(miner_address)s,
                    %(coin)s, %(status)s, %(current_hashrate)s,
                    %(hashrate_unit)s, %(shares_per_second)s,
                    %(accepted_shares)s, %(rejected_shares)s,
                    %(last_share_at)s::TIMESTAMPTZ, %(source_system)s,
                    %(source_worker_id)s, %(classification_source)s,
                    %(classification_confidence)s, %(identity)s,
                    %(observed_state)s, %(metadata)s, NOW(), NOW(), NOW(), NOW()
                )
                ON CONFLICT (worker_id) DO UPDATE SET
                    worker_type = EXCLUDED.worker_type,
                    hardware_type = EXCLUDED.hardware_type,
                    display_name = EXCLUDED.display_name,
                    asset_id = EXCLUDED.asset_id,
                    asset_matched = EXCLUDED.asset_matched,
                    reconciliation_status = EXCLUDED.reconciliation_status,
                    pool_id = EXCLUDED.pool_id,
                    pool_instance_id = EXCLUDED.pool_instance_id,
                    native_pool_id = EXCLUDED.native_pool_id,
                    pool_host = EXCLUDED.pool_host,
                    pool_api_port = EXCLUDED.pool_api_port,
                    worker_name = EXCLUDED.worker_name,
                    miner_address = EXCLUDED.miner_address,
                    coin = EXCLUDED.coin,
                    status = EXCLUDED.status,
                    current_hashrate = EXCLUDED.current_hashrate,
                    hashrate_unit = EXCLUDED.hashrate_unit,
                    shares_per_second = EXCLUDED.shares_per_second,
                    accepted_shares = EXCLUDED.accepted_shares,
                    rejected_shares = EXCLUDED.rejected_shares,
                    last_share_at = EXCLUDED.last_share_at,
                    source_system = EXCLUDED.source_system,
                    source_worker_id = EXCLUDED.source_worker_id,
                    classification_source = EXCLUDED.classification_source,
                    classification_confidence = EXCLUDED.classification_confidence,
                    identity = EXCLUDED.identity,
                    observed_state = EXCLUDED.observed_state,
                    metadata = EXCLUDED.metadata,
                    last_seen_at = NOW(),
                    updated_at = NOW()
                RETURNING *
                """,
                values,
            )
            return dict(cursor.fetchone() or {})


def list_workers() -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM nexus.workers
                ORDER BY display_name, worker_id
                """
            )
            rows = cursor.fetchall()

    return [
        {
            "workerId": row["worker_id"],
            "workerType": row["worker_type"],
            "hardwareType": row["hardware_type"],
            "displayName": row["display_name"],
            "assetId": row["asset_id"],
            "assetMatched": row["asset_matched"],
            "reconciliationStatus": row["reconciliation_status"],
            "poolId": row["pool_id"],
            "poolInstanceId": row["pool_instance_id"],
            "nativePoolId": row["native_pool_id"],
            "poolHost": row["pool_host"],
            "poolApiPort": row["pool_api_port"],
            "workerName": row["worker_name"],
            "minerAddress": row["miner_address"],
            "coin": row["coin"],
            "status": row["status"],
            "currentHashrate": float(row["current_hashrate"]) if row["current_hashrate"] is not None else None,
            "hashrateUnit": row["hashrate_unit"],
            "sharesPerSecond": float(row["shares_per_second"]) if row["shares_per_second"] is not None else None,
            "acceptedShares": float(row["accepted_shares"]) if row["accepted_shares"] is not None else None,
            "rejectedShares": float(row["rejected_shares"]) if row["rejected_shares"] is not None else None,
            "lastShareAt": row["last_share_at"].isoformat() if row["last_share_at"] else None,
            "sourceSystem": row["source_system"],
            "sourceWorkerId": row["source_worker_id"],
            "classificationSource": row["classification_source"],
            "classificationConfidence": float(row["classification_confidence"]) if row["classification_confidence"] is not None else None,
            "identity": row["identity"] or {},
            "observedState": row["observed_state"] or {},
            "metadata": row["metadata"] or {},
            "lastSeenAt": row["last_seen_at"].isoformat() if row["last_seen_at"] else None,
        }
        for row in rows
    ]
