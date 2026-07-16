"""Repository adapter for the existing Nexus alert model."""

from __future__ import annotations

import hashlib
from typing import Any

from psycopg.types.json import Jsonb

from backend.db.connection import get_connection, transaction


def list_enabled_rules() -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM nexus.alert_rules
                WHERE enabled = TRUE
                ORDER BY rule_id
                """
            )
            return cursor.fetchall()


def get_alert_engine_state() -> dict[str, Any]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM nexus.alert_engine_state
                WHERE engine_name = 'platform-alert-engine'
                """
            )
            row = cursor.fetchone()

    return row or {"last_event_id": 0}


def list_events_after(event_id: int) -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM nexus.platform_events
                WHERE event_id > %s
                ORDER BY event_id
                """,
                (event_id,),
            )
            return cursor.fetchall()


def _alert_id(grouping_key: str) -> str:
    digest = hashlib.sha256(
        grouping_key.encode("utf-8")
    ).hexdigest()[:16]

    return f"alert-{digest}"


def open_or_update_alert(
    *,
    rule_id: str,
    event_id: int,
    entity_type: str,
    entity_id: str,
    severity: str,
    title: str,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> str:
    grouping_key = (
        f"{rule_id}:{entity_type}:{entity_id}"
    )


    alert_data = {
        "entityType": entity_type,
        "entityId": entity_id,
        "platformEventId": event_id,
        **(metadata or {}),
    }

    priority = {
        "critical": 100,
        "warning": 70,
        "info": 40,
    }.get(severity, 50)

    recommended_action = {
        "critical": "Investigate the offline resource and restore service.",
        "warning": "Review the resource state change.",
        "info": "Review the recorded configuration change.",
    }.get(severity, "Review the alert.")

    with transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT alert_id
                FROM nexus.alerts
                WHERE grouping_key = %s
                  AND status IN ('open', 'acknowledged')
                FOR UPDATE
                """,
                (grouping_key,),
            )
            existing = cursor.fetchone()

            if existing:
                cursor.execute(
                    """
                    UPDATE nexus.alerts
                    SET
                        event_id = %s,
                        alert_type = %s,
                        severity = %s,
                        title = %s,
                        message = %s,
                        occurrence_count = occurrence_count + 1,
                        last_seen_at = NOW(),
                        data = %s,
                        priority = %s,
                        actionable = TRUE,
                        recommended_action = %s
                    WHERE alert_id = %s
                    """,
                    (
                        None,
                        rule_id,
                        severity,
                        title,
                        message,
                        Jsonb(alert_data),
                        priority,
                        recommended_action,
                        existing["alert_id"],
                    ),
                )
                return "updated"

            cursor.execute(
                """
                INSERT INTO nexus.alerts (
                    alert_id,
                    asset_id,
                    event_id,
                    alert_type,
                    severity,
                    status,
                    title,
                    message,
                    rule_id,
                    occurrence_count,
                    first_seen_at,
                    last_seen_at,
                    acknowledged_by,
                    data,
                    priority,
                    actionable,
                    grouping_key,
                    required_duration_sec,
                    recommended_action
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    'open',
                    %s,
                    %s,
                    %s,
                    1,
                    NOW(),
                    NOW(),
                    '',
                    %s,
                    %s,
                    TRUE,
                    %s,
                    0,
                    %s
                )
                """,
                (
                    _alert_id(grouping_key),
                    None,
                    None,
                    rule_id,
                    severity,
                    title,
                    message,
                    rule_id,
                    Jsonb(alert_data),
                    priority,
                    grouping_key,
                    recommended_action,
                ),
            )

    return "opened"


def resolve_alerts_for_entity(
    *,
    entity_type: str,
    entity_id: str,
) -> int:
    with transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE nexus.alerts
                SET
                    status = 'resolved',
                    resolved_at = NOW(),
                    last_seen_at = NOW()
                WHERE status IN ('open', 'acknowledged')
                  AND data ->> 'entityType' = %s
                  AND data ->> 'entityId' = %s
                """,
                (entity_type, entity_id),
            )
            return cursor.rowcount


def update_alert_engine_state(
    *,
    last_event_id: int,
    status: str,
    evaluated_events: int,
    alerts_opened: int,
    alerts_updated: int,
    alerts_resolved: int,
    error: str = "",
) -> None:
    with transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO nexus.alert_engine_state (
                    engine_name,
                    last_event_id,
                    last_started_at,
                    last_completed_at,
                    last_status,
                    last_error,
                    evaluated_events,
                    alerts_opened,
                    alerts_updated,
                    alerts_resolved,
                    updated_at
                )
                VALUES (
                    'platform-alert-engine',
                    %s,
                    NOW(),
                    NOW(),
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    NOW()
                )
                ON CONFLICT (engine_name)
                DO UPDATE SET
                    last_event_id = EXCLUDED.last_event_id,
                    last_started_at = NOW(),
                    last_completed_at = NOW(),
                    last_status = EXCLUDED.last_status,
                    last_error = EXCLUDED.last_error,
                    evaluated_events = EXCLUDED.evaluated_events,
                    alerts_opened = EXCLUDED.alerts_opened,
                    alerts_updated = EXCLUDED.alerts_updated,
                    alerts_resolved = EXCLUDED.alerts_resolved,
                    updated_at = NOW()
                """,
                (
                    last_event_id,
                    status,
                    error,
                    evaluated_events,
                    alerts_opened,
                    alerts_updated,
                    alerts_resolved,
                ),
            )


def list_alerts(
    limit: int = 100,
) -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM nexus.alerts
                ORDER BY
                    CASE status
                        WHEN 'open' THEN 1
                        WHEN 'acknowledged' THEN 2
                        ELSE 3
                    END,
                    priority DESC,
                    last_seen_at DESC
                LIMIT %s
                """,
                (max(1, min(limit, 1000)),),
            )
            rows = cursor.fetchall()

    return [
        {
            "alertId": row["alert_id"],
            "assetId": row["asset_id"],
            "eventId": row["event_id"],
            "alertType": row["alert_type"],
            "ruleId": row["rule_id"],
            "entityType": (
                row["data"].get("entityType")
                if row["data"]
                else None
            ),
            "entityId": (
                row["data"].get("entityId")
                if row["data"]
                else None
            ),
            "status": row["status"],
            "severity": row["severity"],
            "priority": row["priority"],
            "actionable": row["actionable"],
            "title": row["title"],
            "message": row["message"],
            "occurrenceCount": row["occurrence_count"],
            "firstSeenAt": row["first_seen_at"].isoformat(),
            "lastSeenAt": row["last_seen_at"].isoformat(),
            "acknowledgedAt": (
                row["acknowledged_at"].isoformat()
                if row["acknowledged_at"]
                else None
            ),
            "resolvedAt": (
                row["resolved_at"].isoformat()
                if row["resolved_at"]
                else None
            ),
            "groupingKey": row["grouping_key"],
            "recommendedAction": row["recommended_action"],
            "playbookId": row["playbook_id"],
            "data": row["data"] or {},
        }
        for row in rows
    ]


def alert_summary() -> dict[str, Any]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE status IN ('open', 'acknowledged')
                    ) AS active_count,
                    COUNT(*) FILTER (
                        WHERE status = 'open'
                          AND severity = 'critical'
                    ) AS critical_count,
                    COUNT(*) FILTER (
                        WHERE status = 'open'
                          AND severity = 'warning'
                    ) AS warning_count,
                    COUNT(*) FILTER (
                        WHERE status = 'resolved'
                    ) AS resolved_count
                FROM nexus.alerts
                """
            )
            row = cursor.fetchone()

    return {
        "activeCount": row["active_count"],
        "criticalCount": row["critical_count"],
        "warningCount": row["warning_count"],
        "resolvedCount": row["resolved_count"],
    }
