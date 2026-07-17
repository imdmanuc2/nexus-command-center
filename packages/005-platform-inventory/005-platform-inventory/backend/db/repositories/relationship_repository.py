"""PostgreSQL repository for persistent Nexus topology relationships."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from psycopg.types.json import Jsonb

from backend.db.connection import get_connection, transaction


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
        "metadata": Jsonb(relationship.get("metadata") or {}),
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
