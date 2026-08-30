"""Durable replay protection for signed Nexus peer requests."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.db.connection import get_connection


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def claim_nonce(
    *,
    local_instance_id: str,
    remote_instance_id: str,
    nonce: str,
    request_timestamp: datetime,
    expires_at: datetime,
) -> bool:
    """Atomically claim one peer request nonce.

    Returns True only for the first successful claim of the
    local-instance / remote-instance / nonce tuple.
    """

    local = _text(local_instance_id)
    remote = _text(remote_instance_id)
    nonce_value = _text(nonce)

    if not local:
        raise ValueError(
            "local_instance_id is required"
        )

    if not remote:
        raise ValueError(
            "remote_instance_id is required"
        )

    if not nonce_value:
        raise ValueError(
            "nonce is required"
        )

    if len(nonce_value) != 43:
        raise ValueError(
            "nonce must be canonical 256-bit base64url"
        )

    if request_timestamp.tzinfo is None:
        raise ValueError(
            "request_timestamp must include timezone"
        )

    if expires_at.tzinfo is None:
        raise ValueError(
            "expires_at must include timezone"
        )

    if expires_at <= request_timestamp:
        raise ValueError(
            "expires_at must be after request_timestamp"
        )

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO nexus.nexus_peer_request_nonces (
                    local_instance_id,
                    remote_instance_id,
                    nonce,
                    request_timestamp,
                    expires_at
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                ON CONFLICT (
                    local_instance_id,
                    remote_instance_id,
                    nonce
                )
                DO NOTHING
                """,
                (
                    local,
                    remote,
                    nonce_value,
                    request_timestamp,
                    expires_at,
                ),
            )

            claimed = cursor.rowcount == 1

        connection.commit()

    return claimed


def prune_expired_nonces() -> int:
    """Delete replay records whose retention period has expired."""

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM nexus.nexus_peer_request_nonces
                WHERE expires_at <= NOW()
                """
            )

            deleted = cursor.rowcount

        connection.commit()

    return deleted
