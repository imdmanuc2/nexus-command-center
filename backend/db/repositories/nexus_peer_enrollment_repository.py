"""Repository for short-lived Nexus peer pairing enrollments."""

from __future__ import annotations

from typing import Any

from backend.db.connection import get_connection


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def create_enrollment(
    *,
    enrollment_id: str,
    local_instance_id: str,
    secret_hash: str,
    expires_at,
    requested_remote_instance_id: str = "",
    requested_remote_name: str = "",
    requested_remote_hostname: str = "",
    requested_peer_base_url: str = "",
    requested_public_key_algorithm: str = "",
    requested_public_key: str = "",
    requested_public_key_fingerprint: str = "",
    request_id: str = "",
) -> dict[str, Any]:
    values = {
        "enrollment_id": _text(enrollment_id),
        "local_instance_id": _text(local_instance_id),
        "secret_hash": _text(secret_hash),
    }

    for key, value in values.items():
        if not value:
            raise ValueError(
                f"{key} is required"
            )

    if len(values["secret_hash"]) != 64:
        raise ValueError(
            "secret_hash must be a SHA-256 hex digest"
        )

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO nexus.nexus_peer_enrollments (
                    enrollment_id,
                    local_instance_id,
                    secret_hash,
                    status,
                    requested_remote_instance_id,
                    requested_remote_name,
                    requested_remote_hostname,
                    requested_peer_base_url,
                    requested_public_key_algorithm,
                    requested_public_key,
                    requested_public_key_fingerprint,
                    request_id,
                    expires_at
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    'pending',
                    NULLIF(%s, ''),
                    %s,
                    %s,
                    %s,
                    NULLIF(%s, ''),
                    NULLIF(%s, ''),
                    NULLIF(%s, ''),
                    NULLIF(%s, ''),
                    %s
                )
                RETURNING *
                """,
                (
                    values["enrollment_id"],
                    values["local_instance_id"],
                    values["secret_hash"],
                    _text(requested_remote_instance_id),
                    _text(requested_remote_name),
                    _text(requested_remote_hostname),
                    _text(requested_peer_base_url),
                    _text(requested_public_key_algorithm),
                    _text(requested_public_key),
                    _text(requested_public_key_fingerprint),
                    _text(request_id),
                    expires_at,
                ),
            )

            result = dict(cursor.fetchone())

        connection.commit()

    return result


def get_enrollment(
    enrollment_id: str,
) -> dict[str, Any] | None:
    target = _text(enrollment_id)

    if not target:
        raise ValueError(
            "enrollmentId is required"
        )

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM nexus.nexus_peer_enrollments
                WHERE enrollment_id = %s
                """,
                (target,),
            )

            row = cursor.fetchone()

    return dict(row) if row else None



def list_pending_enrollments() -> list[dict[str, Any]]:
    """Return current unexpired pending enrollment requests."""

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM nexus.nexus_peer_enrollments
                WHERE status = 'pending'
                  AND expires_at > NOW()
                ORDER BY created_at ASC, enrollment_id ASC
                """
            )

            rows = cursor.fetchall()

    return [
        dict(row)
        for row in rows
    ]


def approve_enrollment(
    enrollment_id: str,
) -> dict[str, Any] | None:
    target = _text(enrollment_id)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE nexus.nexus_peer_enrollments
                SET
                    status = 'approved',
                    approved_at = NOW(),
                    updated_at = NOW()
                WHERE enrollment_id = %s
                  AND status = 'pending'
                  AND expires_at > NOW()
                RETURNING *
                """,
                (target,),
            )

            row = cursor.fetchone()

        connection.commit()

    return dict(row) if row else None


def reject_enrollment(
    enrollment_id: str,
) -> dict[str, Any] | None:
    target = _text(enrollment_id)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE nexus.nexus_peer_enrollments
                SET
                    status = 'rejected',
                    rejected_at = NOW(),
                    updated_at = NOW()
                WHERE enrollment_id = %s
                  AND status = 'pending'
                RETURNING *
                """,
                (target,),
            )

            row = cursor.fetchone()

        connection.commit()

    return dict(row) if row else None


def expire_enrollment(
    enrollment_id: str,
) -> dict[str, Any] | None:
    target = _text(enrollment_id)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE nexus.nexus_peer_enrollments
                SET
                    status = 'expired',
                    updated_at = NOW()
                WHERE enrollment_id = %s
                  AND status IN (
                      'pending',
                      'approved'
                  )
                  AND expires_at <= NOW()
                RETURNING *
                """,
                (target,),
            )

            row = cursor.fetchone()

        connection.commit()

    return dict(row) if row else None


def consume_approved_enrollment(
    enrollment_id: str,
) -> dict[str, Any] | None:
    target = _text(enrollment_id)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE nexus.nexus_peer_enrollments
                SET
                    status = 'used',
                    used_at = NOW(),
                    updated_at = NOW()
                WHERE enrollment_id = %s
                  AND status = 'approved'
                  AND expires_at > NOW()
                RETURNING *
                """,
                (target,),
            )

            row = cursor.fetchone()

        connection.commit()

    return dict(row) if row else None


def delete_enrollment(
    enrollment_id: str,
) -> bool:
    target = _text(enrollment_id)

    if not target:
        raise ValueError(
            "enrollmentId is required"
        )

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM nexus.nexus_peer_enrollments
                WHERE enrollment_id = %s
                """,
                (target,),
            )

            deleted = cursor.rowcount > 0

        connection.commit()

    return deleted

def get_enrollment_by_request(
    *,
    local_instance_id: str,
    requested_remote_instance_id: str,
    request_id: str,
) -> dict[str, Any] | None:
    """Return an enrollment by its idempotent request identity."""

    local_id = _text(local_instance_id)
    remote_id = _text(requested_remote_instance_id)
    request_key = _text(request_id)

    if not local_id:
        raise ValueError(
            "local_instance_id is required"
        )

    if not remote_id:
        raise ValueError(
            "requested_remote_instance_id is required"
        )

    if not request_key:
        raise ValueError(
            "request_id is required"
        )

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM nexus.nexus_peer_enrollments
                WHERE local_instance_id = %s
                  AND requested_remote_instance_id = %s
                  AND request_id = %s
                """,
                (
                    local_id,
                    remote_id,
                    request_key,
                ),
            )

            row = cursor.fetchone()

    return dict(row) if row else None
