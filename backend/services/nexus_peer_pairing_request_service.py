"""Initiator orchestration for requesting Nexus peer enrollment.

This service joins three already-separated responsibilities:

1. durable outbound pairing state,
2. signed remote enrollment transport,
3. protected temporary credential storage.

It does not approve or consume enrollment and does not create a peer.
"""

from __future__ import annotations

from typing import Any, Callable

from backend.db.repositories import (
    nexus_peer_outbound_pairing_repository,
)
from backend.services import nexus_peer_enrollment_client_service
from backend.services import nexus_peer_outbound_pairing_service
from backend.services import nexus_peer_pairing_credential_service


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _fail_requesting_pairing(
    *,
    pairing_id: str,
    error: str = "pairing_request_failed",
) -> None:
    try:
        nexus_peer_outbound_pairing_repository.transition_pairing(
            pairing_id=pairing_id,
            expected_status="requesting",
            new_status="failed",
            last_error=_text(error) or "pairing_request_failed",
        )
    except Exception:
        # Preserve the original failure. Recovery tooling can inspect a
        # remaining requesting row without exposing transport details.
        pass


def request_pairing(
    *,
    remote_instance_id: str,
    remote_name: str,
    remote_hostname: str,
    peer_base_url: str,
    remote_public_key_algorithm: str,
    remote_public_key: str,
    remote_public_key_fingerprint: str,
    local_peer_base_url: str,
    timeout: float = (
        nexus_peer_enrollment_client_service
        .DEFAULT_TIMEOUT_SECONDS
    ),
    enrollment_requester: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create and send one outbound Nexus pairing request.

    The one-time remote enrollment credential is encrypted before the
    durable state advances from requesting to pending.
    """

    requester = (
        enrollment_requester
        or nexus_peer_enrollment_client_service
        .request_remote_enrollment
    )

    created = (
        nexus_peer_outbound_pairing_service
        .create_outbound_pairing(
            remote_instance_id=remote_instance_id,
            remote_name=remote_name,
            remote_hostname=remote_hostname,
            peer_base_url=peer_base_url,
            remote_public_key_algorithm=(
                remote_public_key_algorithm
            ),
            remote_public_key=remote_public_key,
            remote_public_key_fingerprint=(
                remote_public_key_fingerprint
            ),
        )
    )

    pairing = created.get("pairing")

    if not isinstance(pairing, dict):
        raise RuntimeError(
            "Outbound pairing creation returned invalid state"
        )

    pairing_id = _text(
        pairing.get("pairingId")
    )

    status = _text(
        pairing.get("status")
    )

    if not pairing_id:
        raise RuntimeError(
            "Outbound pairing state is missing pairingId"
        )

    if not bool(created.get("created")):
        return {
            "status": "ok",
            "created": False,
            "pairing": pairing,
        }

    if status != "requesting":
        raise RuntimeError(
            "New outbound pairing is not requesting"
        )

    try:
        response = requester(
            remote_instance_id=_text(
                remote_instance_id
            ),
            peer_base_url=_text(
                peer_base_url
            ),
            local_peer_base_url=_text(
                local_peer_base_url
            ),
            timeout=timeout,
        )
    except Exception:
        _fail_requesting_pairing(
            pairing_id=pairing_id,
        )
        raise

    if not isinstance(response, dict):
        _fail_requesting_pairing(
            pairing_id=pairing_id,
        )
        raise RuntimeError(
            "Enrollment requester returned invalid response"
        )

    enrollment_id = _text(
        response.get("enrollmentId")
    )

    enrollment_status = _text(
        response.get("enrollmentStatus")
    )

    enrollment_secret = _text(
        response.get("enrollmentSecret")
    )

    expires_at = response.get(
        "expiresAt"
    )

    if (
        not enrollment_id
        or enrollment_status != "pending"
        or not enrollment_secret
        or not expires_at
    ):
        _fail_requesting_pairing(
            pairing_id=pairing_id,
        )
        raise RuntimeError(
            "Enrollment requester returned incomplete response"
        )

    try:
        (
            nexus_peer_pairing_credential_service
            .store_credential(
                pairing_id=pairing_id,
                enrollment_secret=enrollment_secret,
            )
        )
    except Exception:
        _fail_requesting_pairing(
            pairing_id=pairing_id,
        )
        raise

    try:
        row = (
            nexus_peer_outbound_pairing_repository
            .transition_pairing(
                pairing_id=pairing_id,
                expected_status="requesting",
                new_status="pending",
                remote_enrollment_id=enrollment_id,
                expires_at=expires_at,
            )
        )
    except Exception:
        try:
            (
                nexus_peer_pairing_credential_service
                .delete_credential(
                    pairing_id=pairing_id,
                )
            )
        finally:
            _fail_requesting_pairing(
                pairing_id=pairing_id,
            )
        raise

    return {
        "status": "ok",
        "created": True,
        "pairing": {
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
        },
    }
