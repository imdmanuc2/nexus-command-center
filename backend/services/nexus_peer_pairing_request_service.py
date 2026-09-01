"""Initiator orchestration for requesting Nexus peer enrollment.

This service joins three already-separated responsibilities:

1. durable outbound pairing state,
2. signed remote enrollment transport,
3. protected temporary credential storage.

It does not approve or consume enrollment and does not create a peer.
"""

from __future__ import annotations

import hashlib
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

    is_new = bool(
        created.get("created")
    )

    if not is_new:
        if status != "requesting":
            return {
                "status": "ok",
                "created": False,
                "pairing": pairing,
            }

        try:
            enrollment_secret = (
                nexus_peer_pairing_credential_service
                .load_credential(
                    pairing_id=pairing_id,
                )
            )
        except Exception as exc:
            raise RuntimeError(
                "Existing requesting pairing cannot be "
                "retried because its enrollment capability "
                "is unavailable"
            ) from exc

        if not _text(enrollment_secret):
            raise RuntimeError(
                "Existing requesting pairing cannot be "
                "retried because its enrollment capability "
                "is unavailable"
            )
    else:
        if status != "requesting":
            raise RuntimeError(
                "New outbound pairing is not requesting"
            )

        try:
            enrollment_secret = (
                nexus_peer_pairing_credential_service
                .generate_credential()
            )

            if not _text(enrollment_secret):
                raise RuntimeError(
                    "Enrollment capability generation failed"
                )

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

    capability_hash = hashlib.sha256(
        enrollment_secret.encode("utf-8")
    ).hexdigest()

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
            pairing_id=pairing_id,
            capability_hash=capability_hash,
            timeout=timeout,
        )
    except Exception:
        # Preserve both the requesting row and encrypted capability.
        # The receiver may already have committed this request before
        # the transport failed. A recovery path can safely retry with
        # the same pairingId and capability hash.
        raise

    if not isinstance(response, dict):
        raise RuntimeError(
            "Enrollment requester returned invalid response"
        )

    enrollment_id = _text(
        response.get("enrollmentId")
    )

    enrollment_status = _text(
        response.get("enrollmentStatus")
    )

    expires_at = response.get(
        "expiresAt"
    )

    if (
        not enrollment_id
        or enrollment_status != "pending"
        or not expires_at
    ):
        raise RuntimeError(
            "Enrollment requester returned incomplete response"
        )

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
        # The receiver may already have committed this enrollment.
        # Preserve requesting state and the encrypted initiator-owned
        # capability so an exact retry can resend the same pairingId
        # and capabilityHash.
        raise

    return {
        "status": "ok",
        "created": is_new,
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
