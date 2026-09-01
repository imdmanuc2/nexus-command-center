"""Persistence for initiator-side Nexus pairing state."""

from __future__ import annotations

from typing import Any

from backend.db.connection import get_connection


ACTIVE_STATUSES = {
    "requesting",
    "pending",
    "approved",
    "completing",
}


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def create_pairing(
    *,
    pairing_id: str,
    local_instance_id: str,
    remote_instance_id: str,
    remote_name: str,
    remote_hostname: str,
    peer_base_url: str,
    remote_public_key_algorithm: str = "",
    remote_public_key: str = "",
    remote_public_key_fingerprint: str = "",
) -> dict[str, Any]:
    values = {
        "pairing_id": _text(pairing_id),
        "local_instance_id": _text(local_instance_id),
        "remote_instance_id": _text(remote_instance_id),
        "remote_name": _text(remote_name),
        "remote_hostname": _text(remote_hostname),
        "peer_base_url": _text(peer_base_url),
    }

    for key, value in values.items():
        if not value:
            raise ValueError(f"{key} is required")

    algorithm = _text(remote_public_key_algorithm)
    public_key = _text(remote_public_key)
    fingerprint = _text(remote_public_key_fingerprint)

    populated = sum(
        bool(value)
        for value in (
            algorithm,
            public_key,
            fingerprint,
        )
    )

    if populated not in {0, 3}:
        raise ValueError(
            "Remote machine identity must include algorithm, "
            "public key, and fingerprint together"
        )

    if algorithm and algorithm != "Ed25519":
        raise ValueError(
            "Unsupported remote public-key algorithm"
        )

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO nexus.nexus_peer_outbound_pairings (
                    pairing_id,
                    local_instance_id,
                    remote_instance_id,
                    remote_name,
                    remote_hostname,
                    peer_base_url,
                    remote_public_key_algorithm,
                    remote_public_key,
                    remote_public_key_fingerprint,
                    status
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    NULLIF(%s, ''),
                    NULLIF(%s, ''),
                    NULLIF(%s, ''),
                    'requesting'
                )
                RETURNING *
                """,
                (
                    values["pairing_id"],
                    values["local_instance_id"],
                    values["remote_instance_id"],
                    values["remote_name"],
                    values["remote_hostname"],
                    values["peer_base_url"],
                    algorithm,
                    public_key,
                    fingerprint,
                ),
            )

            row = cursor.fetchone()

        connection.commit()

    return dict(row)


def get_pairing(
    pairing_id: str,
) -> dict[str, Any] | None:
    target = _text(pairing_id)

    if not target:
        raise ValueError("pairingId is required")

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM nexus.nexus_peer_outbound_pairings
                WHERE pairing_id = %s
                """,
                (target,),
            )

            row = cursor.fetchone()

    return dict(row) if row else None


def get_active_pairing_for_remote(
    *,
    local_instance_id: str,
    remote_instance_id: str,
) -> dict[str, Any] | None:
    local_id = _text(local_instance_id)
    remote_id = _text(remote_instance_id)

    if not local_id or not remote_id:
        raise ValueError(
            "localInstanceId and remoteInstanceId are required"
        )

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM nexus.nexus_peer_outbound_pairings
                WHERE local_instance_id = %s
                  AND remote_instance_id = %s
                  AND status IN (
                      'requesting',
                      'pending',
                      'approved',
                      'completing'
                  )
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (
                    local_id,
                    remote_id,
                ),
            )

            row = cursor.fetchone()

    return dict(row) if row else None


def list_pairings(
    local_instance_id: str,
) -> list[dict[str, Any]]:
    local_id = _text(local_instance_id)

    if not local_id:
        raise ValueError("localInstanceId is required")

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM nexus.nexus_peer_outbound_pairings
                WHERE local_instance_id = %s
                ORDER BY created_at DESC, pairing_id DESC
                """,
                (local_id,),
            )

            rows = cursor.fetchall()

    return [
        dict(row)
        for row in rows
    ]
