from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from datetime import datetime
from typing import Any

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

def upsert_context(
    *,
    context_key: str,
    context_payload: dict[str, Any],
    source_state: dict[str, Any],
    context_version: str = "v1",
) -> None:
    with transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO nexus.platform_context_snapshots (
                    context_key,
                    context_version,
                    context_payload,
                    generated_at,
                    source_state,
                    updated_at
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    NOW(),
                    %s,
                    NOW()
                )
                ON CONFLICT (context_key)
                DO UPDATE SET
                    context_version = EXCLUDED.context_version,
                    context_payload = EXCLUDED.context_payload,
                    generated_at = NOW(),
                    source_state = EXCLUDED.source_state,
                    updated_at = NOW()
                """,
                (
                    context_key,
                    context_version,
                    Jsonb(_json_safe(context_payload)),
                    Jsonb(_json_safe(source_state)),
                ),
            )


def get_context(context_key: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM nexus.platform_context_snapshots
                WHERE context_key = %s
                """,
                (context_key,),
            )
            row = cursor.fetchone()

    if not row:
        return None

    return {
        "contextKey": row["context_key"],
        "contextVersion": row["context_version"],
        "generatedAt": row["generated_at"].isoformat(),
        "context": row["context_payload"] or {},
        "sourceState": row["source_state"] or {},
    }


def list_contexts() -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM nexus.platform_context_snapshots
                ORDER BY context_key
                """
            )
            rows = cursor.fetchall()

    return [
        {
            "contextKey": row["context_key"],
            "contextVersion": row["context_version"],
            "generatedAt": row["generated_at"].isoformat(),
            "context": row["context_payload"] or {},
            "sourceState": row["source_state"] or {},
        }
        for row in rows
    ]


def update_builder_state(
    *,
    status: str,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    error: str = "",
    contexts_written: int = 0,
) -> None:
    with transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO nexus.ai_context_builder_state (
                    builder_name,
                    last_started_at,
                    last_completed_at,
                    last_status,
                    last_error,
                    contexts_written,
                    updated_at
                )
                VALUES (
                    'platform-ai-context-builder',
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    NOW()
                )
                ON CONFLICT (builder_name)
                DO UPDATE SET
                    last_started_at = COALESCE(
                        EXCLUDED.last_started_at,
                        nexus.ai_context_builder_state.last_started_at
                    ),
                    last_completed_at = COALESCE(
                        EXCLUDED.last_completed_at,
                        nexus.ai_context_builder_state.last_completed_at
                    ),
                    last_status = EXCLUDED.last_status,
                    last_error = EXCLUDED.last_error,
                    contexts_written = EXCLUDED.contexts_written,
                    updated_at = NOW()
                """,
                (
                    started_at,
                    completed_at,
                    status,
                    error,
                    contexts_written,
                ),
            )
