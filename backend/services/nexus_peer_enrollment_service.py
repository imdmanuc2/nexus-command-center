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
from backend.services import nexus_peer_settings_service


DEFAULT_TTL_SECONDS = 900
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
        "requestedRemoteInstanceId":
            row.get("requested_remote_instance_id"),
        "requestedRemoteName":
            row.get("requested_remote_name") or "",
        "requestedRemoteHostname":
            row.get("requested_remote_hostname") or "",
        "requestedPeerBaseUrl":
            row.get("requested_peer_base_url") or "",
        "requestedPublicKeyAlgorithm":
            row.get("requested_public_key_algorithm") or "",
        "requestedPublicKey":
            row.get("requested_public_key") or "",
        "requestedPublicKeyFingerprint":
            row.get("requested_public_key_fingerprint") or "",
        "expiresAt": row["expires_at"],
        "approvedAt": row.get("approved_at"),
        "rejectedAt": row.get("rejected_at"),
        "usedAt": row.get("used_at"),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _operator_connection_request(
    row: dict[str, Any],
) -> dict[str, Any]:
    """Project only fields needed for an operator approval decision."""

    return {
        "enrollmentId":
            row["enrollment_id"],
        "status":
            row["status"],
        "requestedRemoteInstanceId":
            row.get(
                "requested_remote_instance_id"
            ),
        "requestedRemoteName":
            row.get(
                "requested_remote_name"
            ) or "",
        "requestedRemoteHostname":
            row.get(
                "requested_remote_hostname"
            ) or "",
        "requestedPublicKeyFingerprint":
            row.get(
                "requested_public_key_fingerprint"
            ) or "",
        "expiresAt":
            row["expires_at"],
        "createdAt":
            row["created_at"],
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



def list_pending_connection_requests() -> dict[str, Any]:
    """List operator-visible pending Nexus connection requests."""

    settings = (
        nexus_peer_repository
        .get_local_peer_settings()
    )

    if not settings:
        raise RuntimeError(
            "Local peer settings are not initialized"
        )

    enabled = bool(
        settings.get("allow_peer_connections")
    )

    if not enabled:
        return {
            "status": "ok",
            "enabled": False,
            "count": 0,
            "requests": [],
        }

    rows = (
        nexus_peer_enrollment_repository
        .list_pending_enrollments()
    )

    requests = [
        _operator_connection_request(row)
        for row in rows
    ]

    return {
        "status": "ok",
        "enabled": True,
        "count": len(requests),
        "requests": requests,
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




def complete_remote_enrollment(
    *,
    enrollment_id: str,
    pairing_id: str,
    authenticated_remote_instance_id: str,
    enrollment_secret: str,
) -> dict[str, Any]:
    """Complete an authenticated remote pairing enrollment atomically."""

    _require_connections_enabled()

    enrollment_key = str(
        enrollment_id or ""
    ).strip()

    pairing_key = str(
        pairing_id or ""
    ).strip()

    authenticated_remote = str(
        authenticated_remote_instance_id
        or ""
    ).strip()

    capability = str(
        enrollment_secret or ""
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
        raise PermissionError(
            "Authenticated remote instance is required"
        )

    if not capability:
        raise PermissionError(
            "Enrollment capability is required"
        )

    supplied_hash = _hash_secret(
        capability
    )

    result = (
        nexus_peer_enrollment_repository
        .complete_enrollment_atomic(
            enrollment_id=enrollment_key,
            pairing_id=pairing_key,
            authenticated_remote_instance_id=
                authenticated_remote,
            supplied_secret_hash=supplied_hash,
        )
    )

    enrollment = dict(
        result.get("enrollment") or {}
    )

    peer = dict(
        result.get("peer") or {}
    )

    if (
        str(
            enrollment.get(
                "enrollment_id"
            )
            or ""
        ).strip()
        != enrollment_key
    ):
        raise RuntimeError(
            "Completion enrollment identity mismatch"
        )

    if (
        str(
            enrollment.get(
                "request_id"
            )
            or ""
        ).strip()
        != pairing_key
    ):
        raise RuntimeError(
            "Completion pairing identity mismatch"
        )

    if (
        str(
            enrollment.get("status")
            or ""
        ).strip()
        != "used"
    ):
        raise RuntimeError(
            "Completion enrollment is not consumed"
        )

    local_instance_id = str(
        enrollment.get(
            "local_instance_id"
        )
        or ""
    ).strip()

    remote_instance_id = str(
        enrollment.get(
            "requested_remote_instance_id"
        )
        or ""
    ).strip()

    if (
        not remote_instance_id
        or remote_instance_id
        != authenticated_remote
    ):
        raise RuntimeError(
            "Completion authenticated remote identity mismatch"
        )

    peer_local_instance_id = str(
        peer.get(
            "local_instance_id"
        )
        or ""
    ).strip()

    peer_remote_instance_id = str(
        peer.get(
            "remote_instance_id"
        )
        or ""
    ).strip()

    if (
        not local_instance_id
        or peer_local_instance_id
        != local_instance_id
        or peer_remote_instance_id
        != remote_instance_id
    ):
        raise RuntimeError(
            "Completion peer identity mismatch"
        )

    expected_machine_identity = {
        "public_key_algorithm":
            str(
                enrollment.get(
                    "requested_public_key_algorithm"
                )
                or ""
            ).strip(),
        "public_key":
            str(
                enrollment.get(
                    "requested_public_key"
                )
                or ""
            ).strip(),
        "public_key_fingerprint":
            str(
                enrollment.get(
                    "requested_public_key_fingerprint"
                )
                or ""
            ).strip(),
    }

    if any(
        not value
        for value
        in expected_machine_identity.values()
    ):
        raise RuntimeError(
            "Completion enrollment machine identity is incomplete"
        )

    if any(
        str(peer.get(name) or "").strip()
        != value
        for name, value
        in expected_machine_identity.items()
    ):
        raise RuntimeError(
            "Completion peer machine identity mismatch"
        )

    return {
        "status":
            "connected",
        "enrollmentId":
            enrollment_key,
        "pairingId":
            pairing_key,
        "localInstanceId":
            local_instance_id,
        "remoteInstanceId":
            remote_instance_id,
        "peerId":
            str(
                peer.get("peer_id")
                or ""
            ).strip(),
        "created":
            bool(
                result.get("created")
            ),
    }

def establish_consumed_enrollment_peer(
    *,
    enrollment_id: str,
) -> dict[str, Any]:
    """Register a durable peer from a consumed enrollment proof.

    The enrollment must already have completed explicit approval and
    one-time secret consumption. No credential or enrollment secret is
    accepted, persisted, or returned by this operation.
    """

    _require_connections_enabled()

    enrollment_key = _text(enrollment_id)

    if not enrollment_key:
        raise ValueError(
            "enrollmentId is required"
        )

    row = (
        nexus_peer_enrollment_repository
        .get_enrollment(enrollment_key)
    )

    if row is None:
        raise PermissionError(
            "Enrollment is invalid"
        )

    if row["status"] != "used":
        raise PermissionError(
            "Enrollment has not been consumed"
        )

    if row.get("approved_at") is None:
        raise PermissionError(
            "Enrollment was not approved"
        )

    if row.get("used_at") is None:
        raise PermissionError(
            "Enrollment has not been consumed"
        )

    remote_instance_id = _text(
        row.get("requested_remote_instance_id")
    )
    remote_name = _text(
        row.get("requested_remote_name")
    )
    remote_hostname = _text(
        row.get("requested_remote_hostname")
    )
    peer_base_url = _text(
        row.get("requested_peer_base_url")
    )
    public_key_algorithm = _text(
        row.get("requested_public_key_algorithm")
    )
    public_key = _text(
        row.get("requested_public_key")
    )
    public_key_fingerprint = _text(
        row.get("requested_public_key_fingerprint")
    )

    if not remote_instance_id:
        raise ValueError(
            "Enrollment remote instanceId is missing"
        )

    if not remote_name:
        raise ValueError(
            "Enrollment remote name is missing"
        )

    if not remote_hostname:
        raise ValueError(
            "Enrollment remote hostname is missing"
        )

    if not peer_base_url:
        raise ValueError(
            "Enrollment peerBaseUrl is missing"
        )

    identity_document = {
        "status": "ok",
        "protocol": {
            "name": "seymour-nexus-peer",
            "version": "1",
        },
        "instance": {
            "instanceId": remote_instance_id,
            "organizationId": "",
            "siteId": "",
            "name": remote_name,
            "hostname": remote_hostname,
            "identitySource": "approved-enrollment",
        },
        "machineIdentity": {
            "algorithm": public_key_algorithm,
            "publicKey": public_key,
            "fingerprint": public_key_fingerprint,
        },
        "capabilities": {
            "peerAwareness": True,
            "federation": False,
            "cmdbExchange": False,
            "discoveryExchange": False,
            "management": False,
            "authorityDelegation": False,
        },
    }

    peer_id = f"peer-{remote_instance_id}"

    registered = (
        nexus_peer_settings_service
        .register_verified_peer(
            peer_id=peer_id,
            identity_document=identity_document,
            peer_base_url=peer_base_url,
        )
    )

    return {
        "status": "ok",
        "established": True,
        "enrollment": _public_enrollment(row),
        "peer": registered["peer"],
    }

def create_remote_pairing_request(
    *,
    remote_instance_id: str,
    remote_name: str,
    remote_hostname: str,
    peer_base_url: str,
    pairing_id: str,
    capability_hash: str,
    public_key_algorithm: str = "",
    public_key: str = "",
    public_key_fingerprint: str = "",
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> dict[str, Any]:
    """Create or recover one pending remote pairing enrollment.

    The requester owns the one-time capability. Only its SHA-256 hash
    crosses the enrollment-request boundary and is stored here.
    """

    settings = _require_connections_enabled()

    remote_id = _text(remote_instance_id)
    name = _text(remote_name)
    hostname = _text(remote_hostname)
    base_url = _text(peer_base_url)
    request_id = _text(pairing_id)
    supplied_hash = _text(capability_hash).lower()

    if not remote_id:
        raise ValueError(
            "remoteInstanceId is required"
        )

    if remote_id == _text(settings.get("instance_id")):
        raise ValueError(
            "Cannot request pairing with the same Nexus"
        )

    if not name:
        raise ValueError(
            "remoteName is required"
        )

    if not hostname:
        raise ValueError(
            "remoteHostname is required"
        )

    if not base_url:
        raise ValueError(
            "peerBaseUrl is required"
        )

    if not request_id:
        raise ValueError(
            "pairingId is required"
        )

    if (
        len(supplied_hash) != 64
        or any(
            character not in "0123456789abcdef"
            for character in supplied_hash
        )
    ):
        raise ValueError(
            "capabilityHash must be a SHA-256 hex digest"
        )

    key_algorithm = _text(
        public_key_algorithm
    )
    key = _text(
        public_key
    )
    key_fingerprint = _text(
        public_key_fingerprint
    )

    key_parts = (
        key_algorithm,
        key,
        key_fingerprint,
    )

    populated_key_parts = sum(
        bool(value)
        for value in key_parts
    )

    if populated_key_parts not in {0, 3}:
        raise ValueError(
            "Requester public-key identity must include "
            "algorithm, public key, and fingerprint together"
        )

    if key_algorithm:
        if key_algorithm != "Ed25519":
            raise ValueError(
                "Unsupported requester public-key algorithm"
            )

        from backend.services import (
            nexus_peer_machine_identity_service
        )

        raw_public_key = (
            nexus_peer_machine_identity_service
            .decode_public_key(key)
        )

        expected_fingerprint = (
            nexus_peer_machine_identity_service
            .public_key_fingerprint(
                raw_public_key
            )
        )

        if key_fingerprint != expected_fingerprint:
            raise ValueError(
                "Requester public-key fingerprint mismatch"
            )

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

    local_instance_id = _text(
        settings.get("instance_id")
    )

    enrollment_id = (
        "enroll-"
        + uuid.uuid4().hex
    )

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(seconds=ttl_seconds)
    )

    row = (
        nexus_peer_enrollment_repository
        .create_enrollment_idempotent(
            enrollment_id=enrollment_id,
            local_instance_id=local_instance_id,
            secret_hash=supplied_hash,
            expires_at=expires_at,
            requested_remote_instance_id=remote_id,
            requested_remote_name=name,
            requested_remote_hostname=hostname,
            requested_peer_base_url=base_url,
            requested_public_key_algorithm=key_algorithm,
            requested_public_key=key,
            requested_public_key_fingerprint=key_fingerprint,
            request_id=request_id,
        )
    )

    exact = (
        hmac.compare_digest(
            _text(row.get("secret_hash")),
            supplied_hash,
        )
        and _text(
            row.get(
                "requested_remote_name"
            )
        ) == name
        and _text(
            row.get(
                "requested_remote_hostname"
            )
        ) == hostname
        and _text(
            row.get(
                "requested_peer_base_url"
            )
        ) == base_url
        and _text(
            row.get(
                "requested_public_key_algorithm"
            )
        ) == key_algorithm
        and _text(
            row.get(
                "requested_public_key"
            )
        ) == key
        and _text(
            row.get(
                "requested_public_key_fingerprint"
            )
        ) == key_fingerprint
    )

    if not exact:
        raise PermissionError(
            "Pairing request conflicts with existing enrollment"
        )

    created = (
        _text(row.get("enrollment_id"))
        == enrollment_id
    )

    return {
        "status": "ok",
        "created": created,
        "enrollment": _public_enrollment(row),
    }
