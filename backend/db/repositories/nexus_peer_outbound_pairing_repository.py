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


ALLOWED_TRANSITIONS = {
    "requesting": {
        "pending",
        "failed",
        "expired",
    },
    "pending": {
        "approved",
        "rejected",
        "failed",
        "expired",
    },
    "approved": {
        "completing",
        "failed",
        "expired",
    },
    "completing": {
        "connected",
        "failed",
        "expired",
    },
}


def transition_pairing(
    *,
    pairing_id: str,
    expected_status: str,
    new_status: str,
    remote_enrollment_id: str | None = None,
    expires_at: Any = None,
    last_error: str = "",
) -> dict[str, Any]:
    """Atomically advance one outbound pairing.

    The expected current state is part of the UPDATE predicate so
    concurrent or repeated callers cannot silently skip lifecycle states.
    """

    target = _text(pairing_id)
    expected = _text(expected_status)
    destination = _text(new_status)

    if not target:
        raise ValueError(
            "pairingId is required"
        )

    allowed = ALLOWED_TRANSITIONS.get(
        expected,
        set(),
    )

    if destination not in allowed:
        raise ValueError(
            "Invalid outbound pairing state transition: "
            f"{expected} -> {destination}"
        )

    enrollment_id = (
        None
        if remote_enrollment_id is None
        else _text(remote_enrollment_id)
    )

    error = _text(last_error)

    timestamp_column = {
        "pending": "requested_at",
        "approved": "approved_at",
        "rejected": "rejected_at",
        "connected": "connected_at",
    }.get(destination)

    assignments = [
        "status = %s",
        "updated_at = NOW()",
    ]

    parameters: list[Any] = [
        destination,
    ]

    if enrollment_id is not None:
        assignments.append(
            "remote_enrollment_id = NULLIF(%s, '')"
        )
        parameters.append(
            enrollment_id
        )

    if expires_at is not None:
        assignments.append(
            "expires_at = %s"
        )
        parameters.append(
            expires_at
        )

    if destination == "failed":
        assignments.append(
            "last_error = %s"
        )
        parameters.append(
            error or "pairing_failed"
        )
    else:
        assignments.append(
            "last_error = ''"
        )

    if timestamp_column:
        assignments.append(
            f"{timestamp_column} = NOW()"
        )

    parameters.extend(
        [
            target,
            expected,
        ]
    )

    query = (
        "UPDATE nexus.nexus_peer_outbound_pairings "
        "SET "
        + ", ".join(assignments)
        + " WHERE pairing_id = %s "
        "AND status = %s "
        "RETURNING *"
    )

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                tuple(parameters),
            )

            row = cursor.fetchone()

        connection.commit()

    if row:
        return dict(row)

    current = get_pairing(
        target
    )

    if current is None:
        raise KeyError(
            "Outbound pairing not found"
        )

    raise RuntimeError(
        "Outbound pairing state changed concurrently "
        f"or is not {expected}"
    )



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
