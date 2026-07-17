
"""PostgreSQL repository for canonical worker sessions and activity."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from psycopg.types.json import Jsonb

from backend.db.connection import get_connection, transaction
from backend.db.repositories.identity_reconciliation_repository import (
    record_identity_reconciliation,
)

ACTIVE_STATES = {"active", "idle"}


def _positive(value: Any) -> bool:
    try:
        return float(value or 0) > 0
    except (TypeError, ValueError):
        return False


def derive_activity(worker: dict[str, Any]) -> dict[str, Any]:
    source_system = str(worker.get("sourceSystem") or "miningcore").lower()
    status = str(worker.get("status") or "unknown").lower()

    current_hashrate = (
        worker.get("currentHashrate")
        if worker.get("currentHashrate") is not None
        else worker.get("hashrate")
    )
    shares_per_second = worker.get("sharesPerSecond")
    last_share_at = worker.get("lastShareAt")

    observed = worker.get("observedState") or {}
    metadata = worker.get("metadata") or {}

    connection_confirmed = bool(
        worker.get("connectionConfirmed")
        or observed.get("connectionConfirmed")
        or observed.get("socketConnected")
        or observed.get("connected")
        or metadata.get("connectionConfirmed")
    )

    telemetry_available = bool(
        worker.get("telemetryAvailable")
        or observed.get("telemetryAvailable")
        or observed.get("liveWorkerTelemetry")
        or _positive(current_hashrate)
        or _positive(shares_per_second)
        or last_share_at
    )

    live_evidence = bool(
        connection_confirmed
        or _positive(current_hashrate)
        or _positive(shares_per_second)
        or last_share_at
    )

    if status in {"offline", "stale", "down", "error"}:
        activity_state = "offline" if status != "stale" else "stale"
    elif source_system == "generic-stratum" and not live_evidence:
        activity_state = "unknown"
        connection_confirmed = False
        telemetry_available = False
    elif live_evidence:
        activity_state = "active"
    elif status in {"online", "active", "connected", "mining"}:
        activity_state = "idle"
    else:
        activity_state = "unknown"

    if activity_state in {"offline", "stale", "unknown"}:
        current_hashrate = 0
        shares_per_second = 0

    now = datetime.now(timezone.utc)
    last_hashrate_at = worker.get("lastHashrateAt")
    if _positive(current_hashrate) and not last_hashrate_at:
        last_hashrate_at = now.isoformat()

    last_connected_at = worker.get("lastConnectedAt")
    if connection_confirmed and not last_connected_at:
        last_connected_at = now.isoformat()

    return {
        "activityState": activity_state,
        "connectionConfirmed": connection_confirmed,
        "telemetryAvailable": telemetry_available,
        "currentHashrate": current_hashrate or 0,
        "sharesPerSecond": shares_per_second or 0,
        "lastHashrateAt": last_hashrate_at,
        "lastConnectedAt": last_connected_at,
    }


def upsert_worker(worker: dict[str, Any]) -> dict[str, Any]:
    incoming_id = str(worker.get("workerId") or worker.get("id") or "").strip()
    if not incoming_id:
        raise ValueError("Worker requires workerId or id.")

    source_system = str(worker.get("sourceSystem") or "miningcore").strip()
    source_worker_id = str(
        worker.get("sourceWorkerId") or incoming_id
    ).strip()

    if not source_system or not source_worker_id:
        raise ValueError("Worker requires source identity.")

    activity = derive_activity(worker)

    values = {
        "worker_id": incoming_id,
        "worker_type": str(worker.get("workerType") or "unknown").lower(),
        "hardware_type": str(worker.get("hardwareType") or ""),
        "display_name": str(
            worker.get("displayName") or worker.get("name") or incoming_id
        ),
        "asset_id": worker.get("assetId") or None,
        "asset_matched": bool(
            worker.get("assetMatched", bool(worker.get("assetId")))
        ),
        "reconciliation_status": str(
            worker.get("reconciliationStatus")
            or ("matched" if worker.get("assetId") else "unmatched")
        ),
        "pool_id": worker.get("nativePoolId") or worker.get("poolId") or None,
        "pool_instance_id": worker.get("poolInstanceId") or None,
        "native_pool_id": str(
            worker.get("nativePoolId") or worker.get("poolId") or ""
        ),
        "pool_host": str(worker.get("poolHost") or ""),
        "pool_api_port": worker.get("poolApiPort"),
        "worker_name": str(
            worker.get("workerName") or worker.get("name") or ""
        ),
        "miner_address": str(worker.get("minerAddress") or ""),
        "coin": worker.get("coin"),
        "status": str(worker.get("status") or "unknown"),
        "current_hashrate": activity["currentHashrate"],
        "hashrate_unit": str(worker.get("hashrateUnit") or "H/s"),
        "shares_per_second": activity["sharesPerSecond"],
        "accepted_shares": worker.get("acceptedShares"),
        "rejected_shares": worker.get("rejectedShares"),
        "last_share_at": worker.get("lastShareAt"),
        "source_system": source_system,
        "source_worker_id": source_worker_id,
        "classification_source": str(
            worker.get("classificationSource") or ""
        ),
        "classification_confidence": worker.get(
            "classificationConfidence"
        ),
        "identity": Jsonb(worker.get("identity") or {}),
        "observed_state": Jsonb(worker.get("observedState") or {}),
        "metadata": Jsonb(worker.get("metadata") or {}),
        "activity_state": activity["activityState"],
        "connection_confirmed": activity["connectionConfirmed"],
        "telemetry_available": activity["telemetryAvailable"],
        "last_hashrate_at": activity["lastHashrateAt"],
        "last_connected_at": activity["lastConnectedAt"],
    }

    with transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT worker_id
                FROM nexus.workers
                WHERE source_system = %s
                  AND source_worker_id = %s
                FOR UPDATE
                """,
                (source_system, source_worker_id),
            )
            existing = cursor.fetchone()

            if existing:
                canonical = existing["worker_id"]
                cursor.execute(
                    """
                    UPDATE nexus.workers
                    SET
                        worker_type = %(worker_type)s,
                        hardware_type = %(hardware_type)s,
                        display_name = %(display_name)s,
                        asset_id = %(asset_id)s,
                        asset_matched = %(asset_matched)s,
                        reconciliation_status = %(reconciliation_status)s,
                        pool_id = %(pool_id)s,
                        pool_instance_id = %(pool_instance_id)s,
                        native_pool_id = %(native_pool_id)s,
                        pool_host = %(pool_host)s,
                        pool_api_port = %(pool_api_port)s,
                        worker_name = %(worker_name)s,
                        miner_address = %(miner_address)s,
                        coin = %(coin)s,
                        status = %(status)s,
                        current_hashrate = %(current_hashrate)s,
                        hashrate_unit = %(hashrate_unit)s,
                        shares_per_second = %(shares_per_second)s,
                        accepted_shares = %(accepted_shares)s,
                        rejected_shares = %(rejected_shares)s,
                        last_share_at = %(last_share_at)s::TIMESTAMPTZ,
                        classification_source = %(classification_source)s,
                        classification_confidence =
                            %(classification_confidence)s,
                        identity = %(identity)s,
                        observed_state = %(observed_state)s,
                        metadata = %(metadata)s,
                        activity_state = %(activity_state)s,
                        connection_confirmed =
                            %(connection_confirmed)s,
                        telemetry_available =
                            %(telemetry_available)s,
                        last_hashrate_at =
                            %(last_hashrate_at)s::TIMESTAMPTZ,
                        last_connected_at =
                            %(last_connected_at)s::TIMESTAMPTZ,
                        last_seen_at = NOW(),
                        updated_at = NOW()
                    WHERE worker_id = %(canonical)s
                    RETURNING *
                    """,
                    {**values, "canonical": canonical},
                )
                row = cursor.fetchone()
                action = "reconciled-existing"
            else:
                cursor.execute(
                    """
                    INSERT INTO nexus.workers (
                        worker_id, worker_type, hardware_type,
                        display_name, asset_id, asset_matched,
                        reconciliation_status, pool_id,
                        pool_instance_id, native_pool_id, pool_host,
                        pool_api_port, worker_name, miner_address,
                        coin, status, current_hashrate, hashrate_unit,
                        shares_per_second, accepted_shares,
                        rejected_shares, last_share_at, source_system,
                        source_worker_id, classification_source,
                        classification_confidence, identity,
                        observed_state, metadata, activity_state,
                        connection_confirmed, telemetry_available,
                        last_hashrate_at, last_connected_at,
                        current_session, first_seen_at, last_seen_at,
                        created_at, updated_at
                    )
                    VALUES (
                        %(worker_id)s, %(worker_type)s,
                        %(hardware_type)s, %(display_name)s,
                        %(asset_id)s, %(asset_matched)s,
                        %(reconciliation_status)s, %(pool_id)s,
                        %(pool_instance_id)s, %(native_pool_id)s,
                        %(pool_host)s, %(pool_api_port)s,
                        %(worker_name)s, %(miner_address)s, %(coin)s,
                        %(status)s, %(current_hashrate)s,
                        %(hashrate_unit)s, %(shares_per_second)s,
                        %(accepted_shares)s, %(rejected_shares)s,
                        %(last_share_at)s::TIMESTAMPTZ,
                        %(source_system)s, %(source_worker_id)s,
                        %(classification_source)s,
                        %(classification_confidence)s, %(identity)s,
                        %(observed_state)s, %(metadata)s,
                        %(activity_state)s,
                        %(connection_confirmed)s,
                        %(telemetry_available)s,
                        %(last_hashrate_at)s::TIMESTAMPTZ,
                        %(last_connected_at)s::TIMESTAMPTZ,
                        FALSE, NOW(), NOW(), NOW(), NOW()
                    )
                    RETURNING *
                    """,
                    values,
                )
                row = cursor.fetchone()
                canonical = row["worker_id"]
                action = "inserted-new"

    record_identity_reconciliation(
        entity_type="worker",
        canonical_key=f"{source_system}:{source_worker_id}",
        canonical_id=canonical,
        incoming_id=incoming_id,
        source_system=source_system,
        source_identity=source_worker_id,
        action=action,
        details={
            "assetId": values["asset_id"],
            "poolInstanceId": values["pool_instance_id"],
            "status": values["status"],
            "activityState": values["activity_state"],
        },
    )

    return _serialize_worker(row)


def reconcile_worker_sessions() -> dict[str, Any]:
    """Choose one current session per asset and retire losing sessions."""

    with transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM nexus.workers
                ORDER BY asset_id, last_seen_at DESC, worker_id
                """
            )
            rows = cursor.fetchall()

            by_asset: dict[str, list[dict[str, Any]]] = {}
            unbound: list[dict[str, Any]] = []

            for row in rows:
                if row["asset_id"]:
                    by_asset.setdefault(row["asset_id"], []).append(row)
                else:
                    unbound.append(row)

            winners: set[str] = set()

            def score(row: dict[str, Any]) -> tuple:
                activity = str(row["activity_state"] or "unknown")
                rank = {
                    "active": 5,
                    "idle": 4,
                    "unknown": 3,
                    "stale": 2,
                    "offline": 1,
                }.get(activity, 0)

                return (
                    rank,
                    bool(row["connection_confirmed"]),
                    float(row["current_hashrate"] or 0) > 0,
                    bool(row["last_share_at"]),
                    row["last_seen_at"],
                )

            for asset_rows in by_asset.values():
                winner = max(asset_rows, key=score)
                if winner["activity_state"] in ACTIVE_STATES:
                    winners.add(winner["worker_id"])

            for row in unbound:
                if row["activity_state"] in ACTIVE_STATES:
                    winners.add(row["worker_id"])

            cursor.execute(
                """
                UPDATE nexus.workers
                SET
                    current_session = (worker_id = ANY(%s)),
                    retired_at = CASE
                        WHEN worker_id = ANY(%s) THEN NULL
                        WHEN current_session = TRUE THEN NOW()
                        ELSE retired_at
                    END,
                    activity_state = CASE
                        WHEN asset_id IS NOT NULL
                         AND worker_id <> ALL(%s)
                         AND activity_state IN ('active', 'idle')
                            THEN 'stale'
                        ELSE activity_state
                    END,
                    status = CASE
                        WHEN asset_id IS NOT NULL
                         AND worker_id <> ALL(%s)
                         AND activity_state IN ('active', 'idle')
                            THEN 'stale'
                        ELSE status
                    END,
                    current_hashrate = CASE
                        WHEN worker_id = ANY(%s)
                            THEN current_hashrate
                        ELSE 0
                    END,
                    shares_per_second = CASE
                        WHEN worker_id = ANY(%s)
                            THEN shares_per_second
                        ELSE 0
                    END,
                    updated_at = NOW()
                """,
                (
                    list(winners),
                    list(winners),
                    list(winners),
                    list(winners),
                    list(winners),
                    list(winners),
                ),
            )

            cursor.execute(
                """
                UPDATE nexus.relationships
                SET
                    status = CASE
                        WHEN source_id = ANY(%s) THEN 'active'
                        ELSE 'inactive'
                    END,
                    updated_at = NOW()
                WHERE source_type = 'worker'
                """,
                (list(winners),),
            )

    return {
        "status": "ok",
        "source": "nexus-worker-session-reconciliation",
        "currentSessionCount": len(winners),
    }


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

    return [_serialize_worker(row) for row in rows]


def list_active_workers() -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM nexus.workers
                WHERE current_session = TRUE
                  AND activity_state IN ('active', 'idle')
                  AND (
                      asset_id IS NULL
                      OR worker_id IN (
                          SELECT DISTINCT ON (asset_id) worker_id
                          FROM nexus.workers
                          WHERE current_session = TRUE
                            AND activity_state IN ('active', 'idle')
                            AND asset_id IS NOT NULL
                          ORDER BY asset_id, last_seen_at DESC, worker_id
                      )
                  )
                ORDER BY display_name, worker_id
                """
            )
            rows = cursor.fetchall()

    return [_serialize_worker(row) for row in rows]


def active_worker_invariant() -> dict[str, Any]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE current_session = TRUE
                          AND activity_state IN ('active', 'idle')
                    ) AS active_workers,
                    COUNT(DISTINCT asset_id) FILTER (
                        WHERE current_session = TRUE
                          AND activity_state IN ('active', 'idle')
                          AND asset_id IS NOT NULL
                    ) AS active_assets,
                    COUNT(*) FILTER (
                        WHERE current_session = TRUE
                          AND activity_state IN ('active', 'idle')
                          AND asset_id IS NULL
                    ) AS active_unbound
                FROM nexus.workers
                """
            )
            row = cursor.fetchone()

    expected = row["active_assets"] + row["active_unbound"]

    return {
        "activeWorkerCount": row["active_workers"],
        "distinctActivePhysicalAssets": row["active_assets"],
        "activeUnboundWorkers": row["active_unbound"],
        "expectedWorkerCount": expected,
        "valid": row["active_workers"] == expected,
    }


def _serialize_worker(row: dict[str, Any]) -> dict[str, Any]:
    return {
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
        "activityState": row["activity_state"],
        "connectionConfirmed": row["connection_confirmed"],
        "telemetryAvailable": row["telemetry_available"],
        "currentSession": row["current_session"],
        "retiredAt": (
            row["retired_at"].isoformat()
            if row["retired_at"]
            else None
        ),
        "currentHashrate": row["current_hashrate"] or 0,
        "hashrateUnit": row["hashrate_unit"],
        "sharesPerSecond": row["shares_per_second"] or 0,
        "acceptedShares": row["accepted_shares"],
        "rejectedShares": row["rejected_shares"],
        "lastShareAt": (
            row["last_share_at"].isoformat()
            if row["last_share_at"]
            else None
        ),
        "lastHashrateAt": (
            row["last_hashrate_at"].isoformat()
            if row["last_hashrate_at"]
            else None
        ),
        "lastConnectedAt": (
            row["last_connected_at"].isoformat()
            if row["last_connected_at"]
            else None
        ),
        "sourceSystem": row["source_system"],
        "sourceWorkerId": row["source_worker_id"],
        "classificationSource": row["classification_source"],
        "classificationConfidence": row["classification_confidence"],
        "identity": row["identity"] or {},
        "observedState": row["observed_state"] or {},
        "metadata": row["metadata"] or {},
        "firstSeenAt": row["first_seen_at"].isoformat(),
        "lastSeenAt": row["last_seen_at"].isoformat(),
        "updatedAt": row["updated_at"].isoformat(),
    }
