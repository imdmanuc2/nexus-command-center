"""Initiator-side state for secure Nexus peer pairing."""

from __future__ import annotations

import uuid
from typing import Any

from backend.db.repositories import (
    nexus_peer_outbound_pairing_repository,
)
from backend.services import nexus_instance_service
from backend.services import nexus_peer_machine_identity_service


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _local_instance_id() -> str:
    local = nexus_instance_service.get_local_instance()

    if not local:
        raise RuntimeError(
            "Local Nexus instance is not registered"
        )

    instance_id = _text(
        local.get("instance_id")
        or local.get("instanceId")
    )

    if not instance_id:
        raise RuntimeError(
            "Local Nexus instance identity is invalid"
        )

    return instance_id


def _public_pairing(
    row: dict[str, Any],
) -> dict[str, Any]:
    """Operator-safe projection.

    Network transport details and raw public keys intentionally remain
    server-side.
    """

    return {
        "pairingId": row["pairing_id"],
        "remoteInstanceId": row["remote_instance_id"],
        "remoteName": row.get("remote_name") or "",
        "remoteHostname": row.get("remote_hostname") or "",
        "remotePublicKeyFingerprint":
            row.get("remote_public_key_fingerprint") or "",
        "remoteEnrollmentId":
            row.get("remote_enrollment_id") or "",
        "status": row["status"],
        "expiresAt": row.get("expires_at"),
        "requestedAt": row.get("requested_at"),
        "approvedAt": row.get("approved_at"),
        "rejectedAt": row.get("rejected_at"),
        "connectedAt": row.get("connected_at"),
        "lastError": row.get("last_error") or "",
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def create_outbound_pairing(
    *,
    remote_instance_id: str,
    remote_name: str,
    remote_hostname: str,
    peer_base_url: str,
    remote_public_key_algorithm: str,
    remote_public_key: str,
    remote_public_key_fingerprint: str,
) -> dict[str, Any]:
    """Create local initiator state only.

    This function does not contact the remote Nexus and does not create
    or store an enrollment secret.
    """

    local_instance_id = _local_instance_id()

    remote_id = _text(remote_instance_id)

    if not remote_id:
        raise ValueError(
            "remoteInstanceId is required"
        )

    if remote_id == local_instance_id:
        raise ValueError(
            "Cannot pair Nexus with itself"
        )

    existing = (
        nexus_peer_outbound_pairing_repository
        .get_active_pairing_for_remote(
            local_instance_id=local_instance_id,
            remote_instance_id=remote_id,
        )
    )

    if existing:
        return {
            "status": "ok",
            "created": False,
            "pairing": _public_pairing(existing),
        }

    algorithm = _text(
        remote_public_key_algorithm
    )
    public_key = _text(
        remote_public_key
    )
    fingerprint = _text(
        remote_public_key_fingerprint
    )

    if (
        not algorithm
        or not public_key
        or not fingerprint
    ):
        raise ValueError(
            "Verified remote machine identity is required"
        )

    if algorithm != "Ed25519":
        raise ValueError(
            "Unsupported remote public-key algorithm"
        )

    raw_public_key = (
        nexus_peer_machine_identity_service
        .decode_public_key(public_key)
    )

    calculated_fingerprint = (
        nexus_peer_machine_identity_service
        .public_key_fingerprint(raw_public_key)
    )

    if calculated_fingerprint != fingerprint:
        raise ValueError(
            "Remote public-key fingerprint mismatch"
        )

    row = (
        nexus_peer_outbound_pairing_repository
        .create_pairing(
            pairing_id=(
                "pairing-"
                + uuid.uuid4().hex
            ),
            local_instance_id=local_instance_id,
            remote_instance_id=remote_id,
            remote_name=_text(remote_name),
            remote_hostname=_text(remote_hostname),
            peer_base_url=_text(peer_base_url),
            remote_public_key_algorithm=algorithm,
            remote_public_key=public_key,
            remote_public_key_fingerprint=fingerprint,
        )
    )

    return {
        "status": "ok",
        "created": True,
        "pairing": _public_pairing(row),
    }


def list_outbound_pairings() -> dict[str, Any]:
    local_instance_id = _local_instance_id()

    rows = (
        nexus_peer_outbound_pairing_repository
        .list_pairings(local_instance_id)
    )

    pairings = [
        _public_pairing(row)
        for row in rows
    ]

    return {
        "status": "ok",
        "count": len(pairings),
        "pairings": pairings,
    }
