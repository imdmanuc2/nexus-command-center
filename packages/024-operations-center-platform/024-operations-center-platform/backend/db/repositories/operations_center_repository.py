
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from psycopg.types.json import Jsonb

from backend.db.connection import get_connection, transaction


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, dict):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]

    return value


def save_operations_snapshot(
    *,
    snapshot_key: str,
    health_score: float,
    overall_status: str,
    payload: dict[str, Any],
) -> None:
    safe_payload = _json_safe(payload)

    with transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO nexus.operations_center_snapshots (
                    snapshot_key,
                    health_score,
                    overall_status,
                    payload,
                    generated_at
                )
                VALUES (%s, %s, %s, %s, NOW())
                """,
                (
                    snapshot_key,
                    health_score,
                    overall_status,
                    Jsonb(safe_payload),
                ),
            )

            cursor.execute(
                """
                INSERT INTO nexus.operations_center_state (
                    state_key,
                    last_generated_at,
                    last_status,
                    last_error,
                    health_score,
                    updated_at
                )
                VALUES (%s, NOW(), %s, '', %s, NOW())
                ON CONFLICT (state_key)
                DO UPDATE SET
                    last_generated_at = NOW(),
                    last_status = EXCLUDED.last_status,
                    last_error = '',
                    health_score = EXCLUDED.health_score,
                    updated_at = NOW()
                """,
                (
                    snapshot_key,
                    overall_status,
                    health_score,
                ),
            )


def latest_operations_snapshot(
    snapshot_key: str = "primary",
) -> dict[str, Any] | None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    snapshot_id,
                    snapshot_key,
                    health_score,
                    overall_status,
                    payload,
                    generated_at
                FROM nexus.operations_center_snapshots
                WHERE snapshot_key = %s
                ORDER BY generated_at DESC, snapshot_id DESC
                LIMIT 1
                """,
                (snapshot_key,),
            )
            row = cursor.fetchone()

    if not row:
        return None

    return {
        "snapshotId": row["snapshot_id"],
        "snapshotKey": row["snapshot_key"],
        "healthScore": float(row["health_score"]),
        "overallStatus": row["overall_status"],
        "payload": row["payload"] or {},
        "generatedAt": row["generated_at"].isoformat(),
    }


def prune_operations_snapshots(
    *,
    keep_days: int = 30,
) -> int:
    with transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM nexus.operations_center_snapshots
                WHERE generated_at <
                    NOW() - (%s * INTERVAL '1 day')
                """,
                (keep_days,),
            )
            return cursor.rowcount
