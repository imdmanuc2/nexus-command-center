"""PostgreSQL repository for persistent Nexus topology relationships."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from typing import Any
from uuid import uuid4

from psycopg.types.json import Jsonb

from backend.db.connection import get_connection, transaction


def _json_safe(value):
    """Convert database-native values into JSON-compatible values."""

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

def upsert_relationship(relationship: dict[str, Any]) -> dict[str, Any]:
    relationship_id = str(
        relationship.get("relationshipId")
        or relationship.get("id")
        or f"relationship-{uuid4().hex}"
    )

    values = {
        "relationship_id": relationship_id,
        "source_type": str(relationship.get("sourceType") or "asset"),
        "source_id": str(relationship.get("sourceId") or ""),
        "relationship_type": str(relationship.get("relationshipType") or relationship.get("type") or ""),
        "target_type": str(relationship.get("targetType") or "asset"),
        "target_id": str(relationship.get("targetId") or ""),
        "status": str(relationship.get("status") or "active"),
        "confidence": relationship.get("confidence"),
        "source": str(relationship.get("source") or "platform-inventory"),
        "observed": bool(relationship.get("observed", False)),
        "approved": bool(relationship.get("approved", True)),
        "metadata": Jsonb(_json_safe(relationship.get("metadata") or {})),
    }

    if not values["source_id"] or not values["target_id"] or not values["relationship_type"]:
        raise ValueError("Relationship requires sourceId, targetId, and relationshipType.")

    with transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO nexus.relationships (
                    relationship_id, source_type, source_id,
                    relationship_type, target_type, target_id, status,
                    confidence, source, observed, approved, metadata,
                    first_seen_at, last_seen_at, created_at, updated_at
                )
                VALUES (
                    %(relationship_id)s, %(source_type)s, %(source_id)s,
                    %(relationship_type)s, %(target_type)s, %(target_id)s,
                    %(status)s, %(confidence)s, %(source)s, %(observed)s,
                    %(approved)s, %(metadata)s, NOW(), NOW(), NOW(), NOW()
                )
                ON CONFLICT (
                    source_type, source_id, relationship_type,
                    target_type, target_id
                )
                DO UPDATE SET
                    status = EXCLUDED.status,
                    confidence = EXCLUDED.confidence,
                    source = EXCLUDED.source,
                    observed = EXCLUDED.observed,
                    approved = EXCLUDED.approved,
                    metadata = EXCLUDED.metadata,
                    last_seen_at = NOW(),
                    updated_at = NOW()
                RETURNING *
                """,
                values,
            )
            return dict(cursor.fetchone() or {})



def reconcile_topology_relationships(
    relationships: list[dict[str, Any]],
    *,
    source: str = "platform-topology-reconciliation",
) -> dict[str, int]:
    """Upsert the current topology set and deactivate relationships no longer current."""

    active_keys: set[tuple[str, str, str, str, str]] = set()
    written = 0

    for relationship in relationships:
        payload = {
            **relationship,
            "source": source,
            "status": "active",
            "observed": True,
            "approved": True,
        }
        upsert_relationship(payload)
        active_keys.add((
            str(payload.get("sourceType") or "asset"),
            str(payload.get("sourceId") or ""),
            str(payload.get("relationshipType") or ""),
            str(payload.get("targetType") or "asset"),
            str(payload.get("targetId") or ""),
        ))
        written += 1

    with transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    relationship_id,
                    source_type,
                    source_id,
                    relationship_type,
                    target_type,
                    target_id
                FROM nexus.relationships
                WHERE source = %s
                  AND status = 'active'
                """,
                (source,),
            )
            rows = cursor.fetchall()

            stale_ids = [
                row["relationship_id"]
                for row in rows
                if (
                    row["source_type"],
                    row["source_id"],
                    row["relationship_type"],
                    row["target_type"],
                    row["target_id"],
                ) not in active_keys
            ]

            deactivated = 0
            if stale_ids:
                cursor.execute(
                    """
                    UPDATE nexus.relationships
                    SET
                        status = 'inactive',
                        updated_at = NOW()
                    WHERE relationship_id = ANY(%s)
                    """,
                    (stale_ids,),
                )
                deactivated = cursor.rowcount

    return {
        "written": written,
        "deactivated": deactivated,
    }


def list_active_relationships() -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM nexus.relationships
                WHERE status = 'active'
                  AND approved = TRUE
                ORDER BY
                    source_type,
                    source_id,
                    relationship_type,
                    target_type,
                    target_id
                """
            )
            rows = cursor.fetchall()

    return [
        {
            "relationshipId": row["relationship_id"],
            "sourceType": row["source_type"],
            "sourceId": row["source_id"],
            "relationshipType": row["relationship_type"],
            "targetType": row["target_type"],
            "targetId": row["target_id"],
            "status": row["status"],
            "confidence": (
                float(row["confidence"])
                if row["confidence"] is not None
                else None
            ),
            "source": row["source"],
            "observed": row["observed"],
            "approved": row["approved"],
            "metadata": row["metadata"] or {},
        }
        for row in rows
    ]


def list_relationships() -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM nexus.relationships
                ORDER BY source_type, source_id, relationship_type, target_type, target_id
                """
            )
            rows = cursor.fetchall()

    return [
        {
            "relationshipId": row["relationship_id"],
            "sourceType": row["source_type"],
            "sourceId": row["source_id"],
            "relationshipType": row["relationship_type"],
            "targetType": row["target_type"],
            "targetId": row["target_id"],
            "status": row["status"],
            "confidence": float(row["confidence"]) if row["confidence"] is not None else None,
            "source": row["source"],
            "observed": row["observed"],
            "approved": row["approved"],
            "metadata": row["metadata"] or {},
        }
        for row in rows
    ]

def revoke_relationship(
    *,
    source_type: str,
    source_id: str,
    relationship_type: str,
    target_type: str,
    target_id: str,
    actor_id: str,
    reason: str,
    source: str = "deployment-authority-management",
    correlation_id: str = "",
    execute: bool = False,
) -> dict[str, Any]:
    """Plan or atomically revoke one exact relationship.

    Revocation preserves the relationship as historical CMDB state while
    removing it from active/approved authority projections.
    """

    source_type = str(source_type or "").strip()
    source_id = str(source_id or "").strip()
    relationship_type = str(
        relationship_type or ""
    ).strip()
    target_type = str(target_type or "").strip()
    target_id = str(target_id or "").strip()
    actor_id = str(actor_id or "").strip()
    reason = str(reason or "").strip()
    source = str(source or "").strip()
    correlation_id = str(
        correlation_id or ""
    ).strip()

    if not all(
        (
            source_type,
            source_id,
            relationship_type,
            target_type,
            target_id,
        )
    ):
        raise ValueError(
            "Relationship revocation requires exact "
            "source/relationship/target identity."
        )

    if not actor_id:
        raise ValueError(
            "Relationship revocation requires actorId."
        )

    if not reason:
        raise ValueError(
            "Relationship revocation requires reason."
        )

    if not source:
        raise ValueError(
            "Relationship revocation requires source."
        )

    identity = {
        "sourceType": source_type,
        "sourceId": source_id,
        "relationshipType": relationship_type,
        "targetType": target_type,
        "targetId": target_id,
    }

    if not execute:
        return {
            "status": "planned",
            "executable": True,
            "executionPerformed": False,
            **identity,
        }

    with transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM nexus.relationships
                WHERE source_type = %s
                  AND source_id = %s
                  AND relationship_type = %s
                  AND target_type = %s
                  AND target_id = %s
                FOR UPDATE
                """,
                (
                    source_type,
                    source_id,
                    relationship_type,
                    target_type,
                    target_id,
                ),
            )

            before = cursor.fetchone()

            if not before:
                raise ValueError(
                    "Relationship revocation requires an "
                    "existing canonical relationship."
                )

            before = dict(before)

            if (
                str(before.get("status") or "")
                != "active"
                or not bool(before.get("approved"))
            ):
                raise ValueError(
                    "Relationship revocation requires an "
                    "active approved relationship."
                )

            cursor.execute(
                """
                UPDATE nexus.relationships
                SET
                    status = 'inactive',
                    approved = FALSE,
                    updated_by = %s,
                    updated_at = NOW(),
                    last_seen_at = NOW()
                WHERE relationship_id = %s
                  AND status = 'active'
                  AND approved = TRUE
                RETURNING *
                """,
                (
                    actor_id,
                    before["relationship_id"],
                ),
            )

            after = cursor.fetchone()

            if not after:
                raise RuntimeError(
                    "Relationship authority changed "
                    "during revocation."
                )

            after = dict(after)

            history_id = (
                f"history-{uuid4().hex}"
            )

            history_correlation_id = (
                correlation_id
                or f"corr-{uuid4().hex}"
            )

            cursor.execute(
                """
                INSERT INTO nexus.relationship_history (
                    history_id,
                    relationship_id,
                    action,
                    before_state,
                    after_state,
                    reason,
                    changed_by,
                    source,
                    correlation_id
                )
                VALUES (
                    %s, %s, 'authority.revoked',
                    %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    history_id,
                    after["relationship_id"],
                    Jsonb(_json_safe(before)),
                    Jsonb(_json_safe(after)),
                    reason,
                    actor_id,
                    source,
                    history_correlation_id,
                ),
            )

    return {
        "status": "revoked",
        "executable": True,
        "executionPerformed": True,
        "relationshipId": str(
            after["relationship_id"]
        ),
        **identity,
        "approved": False,
        "relationshipStatus": "inactive",
        "historyId": history_id,
        "correlationId": history_correlation_id,
    }
