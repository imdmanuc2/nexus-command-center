"""Initiator-side signed Nexus enrollment-status reconciliation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from backend.db.repositories import (
    nexus_peer_outbound_pairing_repository,
)
from backend.services import (
    nexus_peer_enrollment_client_service,
)


def _text(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip()


def _public_result(
    row: dict[str, Any],
    *,
    remote_status: str,
    changed: bool,
) -> dict[str, Any]:
    return {
        "status": _text(
            row.get("status")
        ),
        "pairingId": _text(
            row.get("pairing_id")
        ),
        "remoteInstanceId": _text(
            row.get("remote_instance_id")
        ),
        "remoteEnrollmentId": _text(
            row.get("remote_enrollment_id")
        ),
        "remoteStatus": remote_status,
        "changed": bool(changed),
    }


def reconcile_pairing_status(
    *,
    pairing_id: str,
    timeout: float = (
        nexus_peer_enrollment_client_service
        .DEFAULT_TIMEOUT_SECONDS
    ),
    status_requester: (
        Callable[..., dict[str, Any]]
        | None
    ) = None,
) -> dict[str, Any]:
    """Reconcile one pending outbound pairing with signed receiver state.

    This operation deliberately does not complete an approved pairing.
    Approval reconciliation and completion remain separate state-machine
    operations.
    """

    pairing_key = _text(
        pairing_id
    )

    if not pairing_key:
        raise ValueError(
            "pairingId is required"
        )

    pairing = (
        nexus_peer_outbound_pairing_repository
        .get_pairing(
            pairing_key
        )
    )

    if pairing is None:
        raise KeyError(
            "Outbound pairing not found"
        )

    local_status = _text(
        pairing.get("status")
    )

    # Reconciliation is needed only while awaiting the receiver's
    # operator decision. Already-reconciled states are idempotent and
    # perform no network request or state transition.
    if local_status in {
        "approved",
        "rejected",
        "expired",
    }:
        return _public_result(
            pairing,
            remote_status=local_status,
            changed=False,
        )

    if local_status != "pending":
        raise PermissionError(
            "Outbound pairing is not pending approval"
        )

    local_instance_id = _text(
        pairing.get("local_instance_id")
    )

    remote_instance_id = _text(
        pairing.get("remote_instance_id")
    )

    remote_enrollment_id = _text(
        pairing.get("remote_enrollment_id")
    )

    peer_base_url = _text(
        pairing.get("peer_base_url")
    )

    required = {
        "local_instance_id":
            local_instance_id,
        "remote_instance_id":
            remote_instance_id,
        "remote_enrollment_id":
            remote_enrollment_id,
        "peer_base_url":
            peer_base_url,
    }

    missing = [
        name
        for name, value in required.items()
        if not value
    ]

    if missing:
        raise RuntimeError(
            "Outbound pairing status state is incomplete: "
            + ", ".join(missing)
        )

    requester = (
        status_requester
        or nexus_peer_enrollment_client_service
        .request_remote_enrollment_status
    )

    response = requester(
        remote_instance_id=
            remote_instance_id,
        peer_base_url=
            peer_base_url,
        enrollment_id=
            remote_enrollment_id,
        pairing_id=
            pairing_key,
        timeout=
            timeout,
    )

    if not isinstance(
        response,
        dict,
    ):
        raise RuntimeError(
            "Enrollment status requester returned invalid response"
        )

    response_enrollment = _text(
        response.get("enrollmentId")
    )

    response_pairing = _text(
        response.get("pairingId")
    )

    response_local = _text(
        response.get("localInstanceId")
    )

    response_remote = _text(
        response.get("remoteInstanceId")
    )

    remote_status = _text(
        response.get("enrollmentStatus")
    )

    if response_enrollment != remote_enrollment_id:
        raise RuntimeError(
            "Enrollment status response enrollment mismatch"
        )

    if response_pairing != pairing_key:
        raise RuntimeError(
            "Enrollment status response pairing mismatch"
        )

    if response_local != remote_instance_id:
        raise RuntimeError(
            "Enrollment status response remote Nexus mismatch"
        )

    if response_remote != local_instance_id:
        raise RuntimeError(
            "Enrollment status response requester mismatch"
        )

    if remote_status == "pending":
        return _public_result(
            pairing,
            remote_status="pending",
            changed=False,
        )

    if remote_status == "used":
        # There is intentionally no outbound "used" lifecycle state.
        # Seeing receiver-side used while this initiator is still pending
        # means completion occurred outside the expected local lifecycle.
        raise RuntimeError(
            "Remote enrollment is already used while outbound "
            "pairing remains pending"
        )

    if remote_status not in {
        "approved",
        "rejected",
        "expired",
    }:
        raise RuntimeError(
            "Enrollment status requester returned unsupported state"
        )

    row = (
        nexus_peer_outbound_pairing_repository
        .transition_pairing(
            pairing_id=
                pairing_key,
            expected_status=
                "pending",
            new_status=
                remote_status,
        )
    )

    return _public_result(
        row,
        remote_status=remote_status,
        changed=True,
    )
