"""Short-lived, user-approved Nexus peer enrollment lifecycle."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.db.repositories import nexus_peer_enrollment_repository
from backend.db.repositories import nexus_peer_repository


DEFAULT_TTL_SECONDS = 300
MIN_TTL_SECONDS = 30
MAX_TTL_SECONDS = 900


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(
        secret.encode("utf-8")
    ).hexdigest()


def _require_connections_enabled() -> dict[str, Any]:
    settings = nexus_peer_repository.get_local_peer_settings()

    if not settings:
        raise RuntimeError(
            "Local peer settings are not initialized"
        )

    if not bool(
        settings.get("allow_peer_connections")
    ):
        raise PermissionError(
            "Nexus peer connections are disabled"
        )

    return settings


def _public_enrollment(
    row: dict[str, Any],
) -> dict[str, Any]:
    return {
        "enrollmentId": row["enrollment_id"],
        "localInstanceId": row["local_instance_id"],
        "status": row["status"],
        "expiresAt": row["expires_at"],
        "approvedAt": row.get("approved_at"),
        "rejectedAt": row.get("rejected_at"),
        "usedAt": row.get("used_at"),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def create_enrollment(
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> dict[str, Any]:
    settings = _require_connections_enabled()

    if not isinstance(ttl_seconds, int):
        raise ValueError(
            "ttlSeconds must be an integer"
        )

    if (
        ttl_seconds < MIN_TTL_SECONDS
        or ttl_seconds > MAX_TTL_SECONDS
    ):
        raise ValueError(
            "ttlSeconds must be between "
            f"{MIN_TTL_SECONDS} and "
            f"{MAX_TTL_SECONDS}"
        )

    enrollment_id = (
        "enroll-"
        + uuid.uuid4().hex
    )

    secret = secrets.token_urlsafe(32)

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(seconds=ttl_seconds)
    )

    row = (
        nexus_peer_enrollment_repository
        .create_enrollment(
            enrollment_id=enrollment_id,
            local_instance_id=str(
                settings["instance_id"]
            ),
            secret_hash=_hash_secret(secret),
            expires_at=expires_at,
        )
    )

    return {
        "status": "ok",
        "enrollment": _public_enrollment(row),
        # Returned once so a later transport layer can deliver it
        # automatically. It is never stored in plaintext.
        "enrollmentSecret": secret,
    }


def get_enrollment(
    enrollment_id: str,
) -> dict[str, Any]:
    row = (
        nexus_peer_enrollment_repository
        .get_enrollment(enrollment_id)
    )

    if row is None:
        raise KeyError(
            "Enrollment not found"
        )

    now = datetime.now(timezone.utc)

    if (
        row["status"] in {"pending", "approved"}
        and row["expires_at"] <= now
    ):
        expired = (
            nexus_peer_enrollment_repository
            .expire_enrollment(enrollment_id)
        )

        if expired:
            row = expired

    return {
        "status": "ok",
        "enrollment": _public_enrollment(row),
    }


def approve_enrollment(
    enrollment_id: str,
) -> dict[str, Any]:
    _require_connections_enabled()

    current = (
        nexus_peer_enrollment_repository
        .get_enrollment(enrollment_id)
    )

    if current is None:
        raise KeyError(
            "Enrollment not found"
        )

    now = datetime.now(timezone.utc)

    if current["expires_at"] <= now:
        (
            nexus_peer_enrollment_repository
            .expire_enrollment(enrollment_id)
        )

        raise PermissionError(
            "Enrollment has expired"
        )

    if current["status"] != "pending":
        raise PermissionError(
            "Enrollment is not pending"
        )

    row = (
        nexus_peer_enrollment_repository
        .approve_enrollment(enrollment_id)
    )

    if row is None:
        raise RuntimeError(
            "Enrollment approval failed"
        )

    return {
        "status": "ok",
        "approved": True,
        "enrollment": _public_enrollment(row),
    }


def reject_enrollment(
    enrollment_id: str,
) -> dict[str, Any]:
    _require_connections_enabled()

    row = (
        nexus_peer_enrollment_repository
        .reject_enrollment(enrollment_id)
    )

    if row is None:
        raise PermissionError(
            "Enrollment cannot be rejected"
        )

    return {
        "status": "ok",
        "rejected": True,
        "enrollment": _public_enrollment(row),
    }


def consume_enrollment(
    *,
    enrollment_id: str,
    enrollment_secret: str,
) -> dict[str, Any]:
    _require_connections_enabled()

    supplied = _text(enrollment_secret)

    if not supplied:
        raise ValueError(
            "enrollmentSecret is required"
        )

    row = (
        nexus_peer_enrollment_repository
        .get_enrollment(enrollment_id)
    )

    if row is None:
        raise PermissionError(
            "Enrollment is invalid"
        )

    now = datetime.now(timezone.utc)

    if (
        row["status"] in {"pending", "approved"}
        and row["expires_at"] <= now
    ):
        (
            nexus_peer_enrollment_repository
            .expire_enrollment(enrollment_id)
        )

        raise PermissionError(
            "Enrollment has expired"
        )

    if row["status"] != "approved":
        raise PermissionError(
            "Enrollment is not approved"
        )

    supplied_hash = _hash_secret(supplied)

    if not hmac.compare_digest(
        supplied_hash,
        row["secret_hash"],
    ):
        raise PermissionError(
            "Enrollment authentication failed"
        )

    used = (
        nexus_peer_enrollment_repository
        .consume_approved_enrollment(
            enrollment_id
        )
    )

    if used is None:
        raise PermissionError(
            "Enrollment has already been used"
        )

    return {
        "status": "ok",
        "consumed": True,
        "enrollment": _public_enrollment(used),
    }
