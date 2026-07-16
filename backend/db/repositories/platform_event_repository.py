from __future__ import annotations

from decimal import Decimal
from datetime import date, datetime

from typing import Any
from psycopg.types.json import Jsonb
from backend.db.connection import get_connection, transaction


def _json_safe(value):
    """Convert PostgreSQL/Python values into JSON-safe structures."""

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
        return [
            _json_safe(item)
            for item in value
        ]

    return value

def get_snapshot(entity_type: str, entity_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM nexus.resource_state_snapshots
                WHERE entity_type = %s AND entity_id = %s
                """,
                (entity_type, entity_id),
            )
            row = cursor.fetchone()
    if not row:
        return None
    return {
        "stateHash": row["state_hash"],
        "statePayload": row["state_payload"] or {},
    }


def upsert_snapshot(
    *,
    entity_type: str,
    entity_id: str,
    state_hash: str,
    state_payload: dict[str, Any],
    changed: bool,
) -> None:
    with transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO nexus.resource_state_snapshots (
                    entity_type, entity_id, state_hash, state_payload,
                    first_observed_at, last_observed_at,
                    last_changed_at, updated_at
                )
                VALUES (%s, %s, %s, %s, NOW(), NOW(), NOW(), NOW())
                ON CONFLICT (entity_type, entity_id)
                DO UPDATE SET
                    state_hash = EXCLUDED.state_hash,
                    state_payload = EXCLUDED.state_payload,
                    last_observed_at = NOW(),
                    last_changed_at = CASE
                        WHEN %s THEN NOW()
                        ELSE nexus.resource_state_snapshots.last_changed_at
                    END,
                    updated_at = NOW()
                """,
                (
                    entity_type,
                    entity_id,
                    state_hash,
                    Jsonb(_json_safe(state_payload)),
                    changed,
                ),
            )


def append_event(
    *,
    event_type: str,
    severity: str,
    entity_type: str,
    entity_id: str,
    title: str,
    message: str = "",
    previous_state: dict[str, Any] | None = None,
    current_state: dict[str, Any] | None = None,
) -> None:
    with transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO nexus.platform_events (
                    event_type, severity, entity_type, entity_id,
                    title, message, previous_state, current_state
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    event_type,
                    severity,
                    entity_type,
                    entity_id,
                    title,
                    message,
                    Jsonb(_json_safe(previous_state or {})),
                    Jsonb(_json_safe(current_state or {})),
                ),
            )


def list_events(limit: int = 100) -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM nexus.platform_events
                ORDER BY occurred_at DESC, event_id DESC
                LIMIT %s
                """,
                (max(1, min(limit, 1000)),),
            )
            rows = cursor.fetchall()

    return [
        {
            "eventId": row["event_id"],
            "eventType": row["event_type"],
            "severity": row["severity"],
            "entityType": row["entity_type"],
            "entityId": row["entity_id"],
            "title": row["title"],
            "message": row["message"],
            "previousState": row["previous_state"] or {},
            "currentState": row["current_state"] or {},
            "occurredAt": row["occurred_at"].isoformat(),
        }
        for row in rows
    ]


def event_summary(hours: int = 24) -> dict[str, Any]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) AS event_count,
                       COUNT(DISTINCT entity_type || ':' || entity_id)
                           AS changed_entity_count,
                       MAX(occurred_at) AS latest_event_at
                FROM nexus.platform_events
                WHERE occurred_at >= NOW() - (%s * INTERVAL '1 hour')
                """,
                (hours,),
            )
            row = cursor.fetchone()
    return {
        "hours": hours,
        "eventCount": row["event_count"],
        "changedEntityCount": row["changed_entity_count"],
        "latestEventAt": (
            row["latest_event_at"].isoformat()
            if row["latest_event_at"] else None
        ),
    }
