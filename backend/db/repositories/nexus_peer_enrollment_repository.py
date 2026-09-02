"""Repository for short-lived Nexus peer pairing enrollments."""

from __future__ import annotations

import hmac
import re

from typing import Any

from psycopg.types.json import Jsonb

from backend.db.connection import get_connection, transaction


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



def create_enrollment_idempotent(
    *,
    enrollment_id: str,
    local_instance_id: str,
    secret_hash: str,
    expires_at,
    requested_remote_instance_id: str,
    requested_remote_name: str = "",
    requested_remote_hostname: str = "",
    requested_peer_base_url: str = "",
    requested_public_key_algorithm: str = "",
    requested_public_key: str = "",
    requested_public_key_fingerprint: str = "",
    request_id: str,
) -> dict[str, Any]:
    """Create or return the winner for one request identity."""

    values = {
        "enrollment_id": _text(enrollment_id),
        "local_instance_id": _text(local_instance_id),
        "secret_hash": _text(secret_hash),
        "requested_remote_instance_id": _text(
            requested_remote_instance_id
        ),
        "request_id": _text(request_id),
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
                    %s,
                    %s,
                    %s,
                    %s,
                    NULLIF(%s, ''),
                    NULLIF(%s, ''),
                    NULLIF(%s, ''),
                    %s,
                    %s
                )
                ON CONFLICT (
                    local_instance_id,
                    requested_remote_instance_id,
                    request_id
                )
                WHERE
                    requested_remote_instance_id IS NOT NULL
                    AND request_id IS NOT NULL
                DO NOTHING
                RETURNING *
                """,
                (
                    values["enrollment_id"],
                    values["local_instance_id"],
                    values["secret_hash"],
                    values[
                        "requested_remote_instance_id"
                    ],
                    _text(requested_remote_name),
                    _text(requested_remote_hostname),
                    _text(requested_peer_base_url),
                    _text(requested_public_key_algorithm),
                    _text(requested_public_key),
                    _text(
                        requested_public_key_fingerprint
                    ),
                    values["request_id"],
                    expires_at,
                ),
            )

            row = cursor.fetchone()

            if row is None:
                cursor.execute(
                    """
                    SELECT *
                    FROM nexus.nexus_peer_enrollments
                    WHERE local_instance_id = %s
                      AND requested_remote_instance_id = %s
                      AND request_id = %s
                    """,
                    (
                        values["local_instance_id"],
                        values[
                            "requested_remote_instance_id"
                        ],
                        values["request_id"],
                    ),
                )

                row = cursor.fetchone()

                if row is None:
                    raise RuntimeError(
                        "Idempotent enrollment winner "
                        "could not be loaded"
                    )

            result = dict(row)

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




def complete_enrollment_atomic(
    *,
    enrollment_id: str,
    pairing_id: str,
    authenticated_remote_instance_id: str,
    supplied_secret_hash: str,
) -> dict[str, Any]:
    """Atomically complete an approved, identity-bound enrollment.

    Plaintext capability material is never accepted here. The locked
    enrollment row is bound to both the initiator-owned pairing request ID
    and the authenticated remote Nexus machine identity before any state
    mutation occurs.
    """

    enrollment_key = _text(enrollment_id)
    pairing_key = _text(pairing_id)
    authenticated_remote = _text(
        authenticated_remote_instance_id
    )
    supplied_hash = _text(
        supplied_secret_hash
    )

    if not enrollment_key:
        raise ValueError(
            "enrollment_id is required"
        )

    if not pairing_key:
        raise ValueError(
            "pairing_id is required"
        )

    if not authenticated_remote:
        raise ValueError(
            "authenticated_remote_instance_id is required"
        )

    if not re.fullmatch(
        r"[0-9a-f]{64}",
        supplied_hash,
    ):
        raise ValueError(
            "supplied_secret_hash must be a lowercase SHA-256 hex digest"
        )

    with transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM nexus.nexus_peer_enrollments
                WHERE enrollment_id = %s
                FOR UPDATE
                """,
                (enrollment_key,),
            )

            enrollment_row = cursor.fetchone()

            if enrollment_row is None:
                raise PermissionError(
                    "Enrollment is invalid"
                )

            enrollment = dict(
                enrollment_row
            )

            stored_pairing_id = _text(
                enrollment.get("request_id")
            )

            if (
                not stored_pairing_id
                or not hmac.compare_digest(
                    pairing_key,
                    stored_pairing_id,
                )
            ):
                raise PermissionError(
                    "Enrollment pairing identity mismatch"
                )

            remote_instance_id = _text(
                enrollment.get(
                    "requested_remote_instance_id"
                )
            )

            if (
                not remote_instance_id
                or not hmac.compare_digest(
                    authenticated_remote,
                    remote_instance_id,
                )
            ):
                raise PermissionError(
                    "Enrollment authenticated remote identity mismatch"
                )

            stored_hash = _text(
                enrollment.get("secret_hash")
            )

            if (
                not stored_hash
                or not hmac.compare_digest(
                    supplied_hash,
                    stored_hash,
                )
            ):
                raise PermissionError(
                    "Enrollment authentication failed"
                )

            status = _text(
                enrollment.get("status")
            )

            remote_name = _text(
                enrollment.get(
                    "requested_remote_name"
                )
            )
            remote_hostname = _text(
                enrollment.get(
                    "requested_remote_hostname"
                )
            )
            peer_base_url = _text(
                enrollment.get(
                    "requested_peer_base_url"
                )
            )
            public_key_algorithm = _text(
                enrollment.get(
                    "requested_public_key_algorithm"
                )
            )
            public_key = _text(
                enrollment.get(
                    "requested_public_key"
                )
            )
            public_key_fingerprint = _text(
                enrollment.get(
                    "requested_public_key_fingerprint"
                )
            )

            required_remote = {
                "requested_remote_instance_id":
                    remote_instance_id,
                "requested_remote_name":
                    remote_name,
                "requested_remote_hostname":
                    remote_hostname,
                "requested_peer_base_url":
                    peer_base_url,
                "requested_public_key_algorithm":
                    public_key_algorithm,
                "requested_public_key":
                    public_key,
                "requested_public_key_fingerprint":
                    public_key_fingerprint,
            }

            missing = [
                name
                for name, value
                in required_remote.items()
                if not value
            ]

            if missing:
                raise ValueError(
                    "Enrollment remote identity is incomplete: "
                    + ", ".join(missing)
                )

            if public_key_algorithm != "Ed25519":
                raise ValueError(
                    "Unsupported enrollment public-key algorithm"
                )

            local_instance_id = _text(
                enrollment.get(
                    "local_instance_id"
                )
            )

            if not local_instance_id:
                raise ValueError(
                    "Enrollment local instanceId is missing"
                )

            if (
                remote_instance_id
                == local_instance_id
            ):
                raise ValueError(
                    "Enrollment cannot target local Nexus"
                )

            peer_id = (
                "peer-"
                + remote_instance_id
            )

            identity_expected = {
                "local_instance_id":
                    local_instance_id,
                "remote_instance_id":
                    remote_instance_id,
                "public_key_algorithm":
                    public_key_algorithm,
                "public_key":
                    public_key,
                "public_key_fingerprint":
                    public_key_fingerprint,
            }

            def validate_peer_identity(
                peer: dict[str, Any],
                *,
                message: str,
            ) -> None:
                conflicting = [
                    name
                    for name, value
                    in identity_expected.items()
                    if _text(peer.get(name))
                    != value
                ]

                if conflicting:
                    raise PermissionError(
                        message
                    )

            if status == "approved":
                if (
                    enrollment.get(
                        "approved_at"
                    )
                    is None
                ):
                    raise PermissionError(
                        "Enrollment was not approved"
                    )

                cursor.execute(
                    """
                    SELECT *
                    FROM nexus.nexus_peers
                    WHERE local_instance_id = %s
                      AND remote_instance_id = %s
                    LIMIT 1
                    FOR UPDATE
                    """,
                    (
                        local_instance_id,
                        remote_instance_id,
                    ),
                )

                existing_peer_row = (
                    cursor.fetchone()
                )

                existing_peer = (
                    dict(existing_peer_row)
                    if existing_peer_row
                    is not None
                    else None
                )

                if existing_peer is not None:
                    validate_peer_identity(
                        existing_peer,
                        message=(
                            "Existing peer identity conflicts "
                            "with enrollment"
                        ),
                    )

                cursor.execute(
                    """
                    UPDATE nexus.nexus_peer_enrollments
                    SET
                        status = 'used',
                        used_at = NOW(),
                        updated_at = NOW()
                    WHERE enrollment_id = %s
                      AND status = 'approved'
                      AND approved_at IS NOT NULL
                      AND expires_at > NOW()
                    RETURNING *
                    """,
                    (enrollment_key,),
                )

                used_row = cursor.fetchone()

                if used_row is None:
                    raise PermissionError(
                        "Approved enrollment is expired or could not be consumed"
                    )

                enrollment = dict(
                    used_row
                )

                if existing_peer is not None:
                    return {
                        "enrollment":
                            enrollment,
                        "peer":
                            existing_peer,
                        "created":
                            False,
                    }

                cursor.execute(
                    """
                    INSERT INTO nexus.nexus_peers (
                        peer_id,
                        local_instance_id,
                        remote_instance_id,
                        organization_id,
                        site_id,
                        name,
                        hostname,
                        peer_base_url,
                        protocol_name,
                        protocol_version,
                        public_key_algorithm,
                        public_key,
                        public_key_fingerprint,
                        status,
                        enabled,
                        peer_awareness,
                        federation_enabled,
                        cmdb_exchange_enabled,
                        discovery_exchange_enabled,
                        management_enabled,
                        authority_delegation_enabled,
                        last_verified_at,
                        last_seen_at,
                        metadata,
                        updated_at
                    )
                    VALUES (
                        %(peer_id)s,
                        %(local_instance_id)s,
                        %(remote_instance_id)s,
                        '',
                        '',
                        %(name)s,
                        %(hostname)s,
                        %(peer_base_url)s,
                        'seymour-nexus-peer',
                        '1',
                        %(public_key_algorithm)s,
                        %(public_key)s,
                        %(public_key_fingerprint)s,
                        'verified',
                        TRUE,
                        TRUE,
                        FALSE,
                        FALSE,
                        FALSE,
                        FALSE,
                        FALSE,
                        NOW(),
                        NOW(),
                        %(metadata)s,
                        NOW()
                    )
                    ON CONFLICT (
                        local_instance_id,
                        remote_instance_id
                    )
                    WHERE remote_instance_id IS NOT NULL
                    DO NOTHING
                    RETURNING *
                    """,
                    {
                        "peer_id":
                            peer_id,
                        "local_instance_id":
                            local_instance_id,
                        "remote_instance_id":
                            remote_instance_id,
                        "name":
                            remote_name,
                        "hostname":
                            remote_hostname,
                        "peer_base_url":
                            peer_base_url,
                        "public_key_algorithm":
                            public_key_algorithm,
                        "public_key":
                            public_key,
                        "public_key_fingerprint":
                            public_key_fingerprint,
                        "metadata":
                            Jsonb({}),
                    },
                )

                peer_row = cursor.fetchone()

                if peer_row is not None:
                    return {
                        "enrollment":
                            enrollment,
                        "peer":
                            dict(peer_row),
                        "created":
                            True,
                    }

                # Defensive race recovery. If another transaction won the
                # peer insert, it must represent exactly the same machine
                # identity. Never overwrite the winner.
                cursor.execute(
                    """
                    SELECT *
                    FROM nexus.nexus_peers
                    WHERE local_instance_id = %s
                      AND remote_instance_id = %s
                    LIMIT 1
                    FOR UPDATE
                    """,
                    (
                        local_instance_id,
                        remote_instance_id,
                    ),
                )

                raced_peer_row = (
                    cursor.fetchone()
                )

                if raced_peer_row is None:
                    raise RuntimeError(
                        "Verified peer could not be established"
                    )

                raced_peer = dict(
                    raced_peer_row
                )

                validate_peer_identity(
                    raced_peer,
                    message=(
                        "Existing peer identity conflicts "
                        "with enrollment"
                    ),
                )

                return {
                    "enrollment":
                        enrollment,
                    "peer":
                        raced_peer,
                    "created":
                        False,
                }

            if status != "used":
                raise PermissionError(
                    "Enrollment is not approved"
                )

            if (
                enrollment.get("approved_at")
                is None
            ):
                raise PermissionError(
                    "Enrollment was not approved"
                )

            if (
                enrollment.get("used_at")
                is None
            ):
                raise PermissionError(
                    "Enrollment has no consumption proof"
                )

            cursor.execute(
                """
                SELECT *
                FROM nexus.nexus_peers
                WHERE local_instance_id = %s
                  AND remote_instance_id = %s
                LIMIT 1
                FOR UPDATE
                """,
                (
                    local_instance_id,
                    remote_instance_id,
                ),
            )

            peer_row = cursor.fetchone()

            if peer_row is None:
                raise PermissionError(
                    "Consumed enrollment has no durable peer"
                )

            peer = dict(
                peer_row
            )

            validate_peer_identity(
                peer,
                message=(
                    "Consumed enrollment peer identity conflicts"
                ),
            )

            return {
                "enrollment":
                    enrollment,
                "peer":
                    peer,
                "created":
                    False,
            }

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
