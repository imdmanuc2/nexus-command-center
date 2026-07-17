from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from psycopg.types.json import Jsonb

from backend.db.connection import get_connection, transaction


def _recommendation_id(rule_id: str, entity_type: str, entity_id: str) -> str:
    raw = f"{rule_id}:{entity_type}:{entity_id}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"rec-{digest}"


def upsert_recommendation(
    *,
    rule_id: str,
    category: str,
    priority: str,
    priority_score: int,
    confidence: float,
    entity_type: str,
    entity_id: str,
    title: str,
    explanation: str,
    recommended_action: str,
    evidence: dict[str, Any],
    expires_at: datetime | None = None,
) -> str:
    recommendation_id = _recommendation_id(
        rule_id,
        entity_type,
        entity_id,
    )

    with transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT recommendation_id
                FROM nexus.recommendations
                WHERE rule_id = %s
                  AND entity_type = %s
                  AND entity_id = %s
                  AND status IN ('open', 'accepted')
                FOR UPDATE
                """,
                (rule_id, entity_type, entity_id),
            )
            existing = cursor.fetchone()

            if existing:
                cursor.execute(
                    """
                    UPDATE nexus.recommendations
                    SET
                        category = %s,
                        priority = %s,
                        priority_score = %s,
                        confidence = %s,
                        title = %s,
                        explanation = %s,
                        recommended_action = %s,
                        evidence = %s,
                        last_generated_at = NOW(),
                        generation_count = generation_count + 1,
                        expires_at = %s,
                        updated_at = NOW()
                    WHERE recommendation_id = %s
                    """,
                    (
                        category,
                        priority,
                        priority_score,
                        confidence,
                        title,
                        explanation,
                        recommended_action,
                        Jsonb(evidence),
                        expires_at,
                        existing["recommendation_id"],
                    ),
                )
                return "updated"

            cursor.execute(
                """
                INSERT INTO nexus.recommendations (
                    recommendation_id,
                    rule_id,
                    category,
                    priority,
                    priority_score,
                    confidence,
                    entity_type,
                    entity_id,
                    title,
                    explanation,
                    recommended_action,
                    evidence,
                    status,
                    expires_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    'open', %s
                )
                """,
                (
                    recommendation_id,
                    rule_id,
                    category,
                    priority,
                    priority_score,
                    confidence,
                    entity_type,
                    entity_id,
                    title,
                    explanation,
                    recommended_action,
                    Jsonb(evidence),
                    expires_at,
                ),
            )
            return "opened"


def resolve_missing_recommendations(
    active_keys: set[tuple[str, str, str]],
) -> int:
    with transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT recommendation_id, rule_id, entity_type, entity_id
                FROM nexus.recommendations
                WHERE status IN ('open', 'accepted')
                """
            )
            rows = cursor.fetchall()

            stale_ids = [
                row["recommendation_id"]
                for row in rows
                if (
                    row["rule_id"],
                    row["entity_type"],
                    row["entity_id"],
                ) not in active_keys
            ]

            if not stale_ids:
                return 0

            cursor.execute(
                """
                UPDATE nexus.recommendations
                SET
                    status = 'completed',
                    completed_at = NOW(),
                    updated_at = NOW()
                WHERE recommendation_id = ANY(%s)
                """,
                (stale_ids,),
            )
            return cursor.rowcount


def list_recommendations(limit: int = 100) -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM nexus.recommendations
                ORDER BY
                    CASE status
                        WHEN 'open' THEN 1
                        WHEN 'accepted' THEN 2
                        ELSE 3
                    END,
                    priority_score DESC,
                    last_generated_at DESC
                LIMIT %s
                """,
                (max(1, min(limit, 1000)),),
            )
            rows = cursor.fetchall()

    return [_serialize(row) for row in rows]


def recommendation_summary() -> dict[str, Any]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE status IN ('open', 'accepted')
                    ) AS active_count,
                    COUNT(*) FILTER (
                        WHERE status = 'open'
                          AND priority IN ('critical', 'high')
                    ) AS high_priority_count,
                    COUNT(*) FILTER (
                        WHERE status = 'completed'
                    ) AS completed_count,
                    MAX(last_generated_at) AS latest_generated_at
                FROM nexus.recommendations
                """
            )
            row = cursor.fetchone()

    return {
        "activeCount": row["active_count"],
        "highPriorityCount": row["high_priority_count"],
        "completedCount": row["completed_count"],
        "latestGeneratedAt": (
            row["latest_generated_at"].isoformat()
            if row["latest_generated_at"]
            else None
        ),
    }


def update_engine_state(
    *,
    status: str,
    evaluated_rules: int,
    opened: int,
    updated: int,
    resolved: int,
    error: str = "",
) -> None:
    with transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO nexus.recommendation_engine_state (
                    engine_name,
                    last_started_at,
                    last_completed_at,
                    last_status,
                    last_error,
                    evaluated_rules,
                    recommendations_opened,
                    recommendations_updated,
                    recommendations_resolved,
                    updated_at
                )
                VALUES (
                    'platform-recommendation-engine',
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
                    last_started_at = NOW(),
                    last_completed_at = NOW(),
                    last_status = EXCLUDED.last_status,
                    last_error = EXCLUDED.last_error,
                    evaluated_rules = EXCLUDED.evaluated_rules,
                    recommendations_opened = EXCLUDED.recommendations_opened,
                    recommendations_updated = EXCLUDED.recommendations_updated,
                    recommendations_resolved = EXCLUDED.recommendations_resolved,
                    updated_at = NOW()
                """,
                (
                    status,
                    error,
                    evaluated_rules,
                    opened,
                    updated,
                    resolved,
                ),
            )


def _serialize(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "recommendationId": row["recommendation_id"],
        "ruleId": row["rule_id"],
        "category": row["category"],
        "priority": row["priority"],
        "priorityScore": row["priority_score"],
        "confidence": row["confidence"],
        "entityType": row["entity_type"],
        "entityId": row["entity_id"],
        "title": row["title"],
        "explanation": row["explanation"],
        "recommendedAction": row["recommended_action"],
        "evidence": row["evidence"] or {},
        "status": row["status"],
        "firstGeneratedAt": row["first_generated_at"].isoformat(),
        "lastGeneratedAt": row["last_generated_at"].isoformat(),
        "acceptedAt": (
            row["accepted_at"].isoformat()
            if row["accepted_at"] else None
        ),
        "dismissedAt": (
            row["dismissed_at"].isoformat()
            if row["dismissed_at"] else None
        ),
        "completedAt": (
            row["completed_at"].isoformat()
            if row["completed_at"] else None
        ),
        "generationCount": row["generation_count"],
        "expiresAt": (
            row["expires_at"].isoformat()
            if row["expires_at"] else None
        ),
    }
