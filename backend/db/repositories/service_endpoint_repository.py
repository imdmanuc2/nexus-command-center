from __future__ import annotations

from typing import Any

from backend.db.connection import get_connection


def _text(value: Any) -> str:
    return (
        ""
        if value is None
        else str(value).strip()
    )


def find_for_subject(
    *,
    subject_type: str,
    subject_id: str,
    service_type: str,
) -> list[dict[str, Any]]:
    subject_type = _text(
        subject_type
    )

    subject_id = _text(
        subject_id
    )

    service_type = _text(
        service_type
    )

    if not subject_type:
        raise ValueError(
            "subject_type is required"
        )

    if not subject_id:
        raise ValueError(
            "subject_id is required"
        )

    if not service_type:
        raise ValueError(
            "service_type is required"
        )

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    endpoint_id,
                    subject_type,
                    subject_id,
                    service_type,
                    protocol,
                    host,
                    port,
                    path,
                    tls_enabled,
                    status,
                    latency_ms,
                    last_checked_at,
                    last_healthy_at,
                    metadata
                FROM nexus.service_endpoints
                WHERE subject_type = %s
                  AND subject_id = %s
                  AND service_type = %s
                ORDER BY endpoint_id
                """,
                (
                    subject_type,
                    subject_id,
                    service_type,
                ),
            )

            rows = cursor.fetchall()

    return [
        dict(row)
        for row in rows
    ]
