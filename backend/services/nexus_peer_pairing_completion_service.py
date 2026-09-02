"""Initiator-side Nexus pairing completion orchestration."""

from __future__ import annotations

from typing import Any, Callable

from backend.db.repositories import (
    nexus_peer_outbound_pairing_repository,
)
from backend.db.repositories import (
    nexus_peer_repository,
)
from backend.services import (
    nexus_peer_enrollment_client_service,
)
from backend.services import (
    nexus_peer_pairing_credential_service,
)
from backend.services import (
    nexus_peer_settings_service,
)


def _text(value: Any) -> str:
    return (
        ""
        if value is None
        else str(value).strip()
    )


def _machine_identity_matches(
    peer: dict[str, Any],
    pairing: dict[str, Any],
) -> bool:
    expected = {
        "local_instance_id":
            _text(
                pairing.get(
                    "local_instance_id"
                )
            ),
        "remote_instance_id":
            _text(
                pairing.get(
                    "remote_instance_id"
                )
            ),
        "public_key_algorithm":
            _text(
                pairing.get(
                    "remote_public_key_algorithm"
                )
            ),
        "public_key":
            _text(
                pairing.get(
                    "remote_public_key"
                )
            ),
        "public_key_fingerprint":
            _text(
                pairing.get(
                    "remote_public_key_fingerprint"
                )
            ),
    }

    return all(
        _text(peer.get(name))
        == value
        for name, value
        in expected.items()
    )


def _safe_identity_document(
    pairing: dict[str, Any],
) -> dict[str, Any]:
    return {
        "status": "ok",
        "protocol": {
            "name":
                "seymour-nexus-peer",
            "version":
                "1",
        },
        "instance": {
            "instanceId":
                _text(
                    pairing.get(
                        "remote_instance_id"
                    )
                ),
            "organizationId":
                "",
            "siteId":
                "",
            "name":
                _text(
                    pairing.get(
                        "remote_name"
                    )
                ),
            "hostname":
                _text(
                    pairing.get(
                        "remote_hostname"
                    )
                ),
            "identitySource":
                "approved-outbound-pairing",
        },
        "machineIdentity": {
            "algorithm":
                _text(
                    pairing.get(
                        "remote_public_key_algorithm"
                    )
                ),
            "publicKey":
                _text(
                    pairing.get(
                        "remote_public_key"
                    )
                ),
            "fingerprint":
                _text(
                    pairing.get(
                        "remote_public_key_fingerprint"
                    )
                ),
        },
        "capabilities": {
            "peerAwareness":
                True,
            "federation":
                False,
            "cmdbExchange":
                False,
            "discoveryExchange":
                False,
            "management":
                False,
            "authorityDelegation":
                False,
        },
    }


def complete_pairing(
    *,
    pairing_id: str,
    timeout: float = (
        nexus_peer_enrollment_client_service
        .DEFAULT_TIMEOUT_SECONDS
    ),
    completion_requester: (
        Callable[..., dict[str, Any]]
        | None
    ) = None,
) -> dict[str, Any]:
    """Complete one approved outbound Nexus pairing.

    The encrypted one-time capability is retained through all recoverable
    failure points and deleted only after durable reciprocal peer state and
    the outbound connected transition both succeed.
    """

    pairing_key = _text(
        pairing_id
    )

    if not pairing_key:
        raise ValueError(
            "pairingId is required"
        )

    requester = (
        completion_requester
        or nexus_peer_enrollment_client_service
        .complete_remote_enrollment_request
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

    status = _text(
        pairing.get("status")
    )

    if status == "connected":
        # Completion may have reached durable connected state before a
        # final temporary-credential deletion failed. A connected retry
        # performs cleanup only: no credential load, network completion,
        # peer mutation, or pairing-state transition.
        (
            nexus_peer_pairing_credential_service
            .delete_credential(
                pairing_id=
                    pairing_key,
            )
        )

        return {
            "status":
                "connected",
            "pairingId":
                pairing_key,
            "remoteInstanceId":
                _text(
                    pairing.get(
                        "remote_instance_id"
                    )
                ),
            "remoteEnrollmentId":
                _text(
                    pairing.get(
                        "remote_enrollment_id"
                    )
                ),
            "created":
                False,
            "alreadyConnected":
                True,
        }

    if status == "approved":
        pairing = (
            nexus_peer_outbound_pairing_repository
            .transition_pairing(
                pairing_id=
                    pairing_key,
                expected_status=
                    "approved",
                new_status=
                    "completing",
            )
        )

        status = "completing"

    if status != "completing":
        raise PermissionError(
            "Outbound pairing is not approved for completion"
        )

    local_instance_id = _text(
        pairing.get(
            "local_instance_id"
        )
    )

    remote_instance_id = _text(
        pairing.get(
            "remote_instance_id"
        )
    )

    remote_enrollment_id = _text(
        pairing.get(
            "remote_enrollment_id"
        )
    )

    peer_base_url = _text(
        pairing.get(
            "peer_base_url"
        )
    )

    algorithm = _text(
        pairing.get(
            "remote_public_key_algorithm"
        )
    )

    public_key = _text(
        pairing.get(
            "remote_public_key"
        )
    )

    fingerprint = _text(
        pairing.get(
            "remote_public_key_fingerprint"
        )
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
        "remote_public_key_algorithm":
            algorithm,
        "remote_public_key":
            public_key,
        "remote_public_key_fingerprint":
            fingerprint,
    }

    missing = [
        name
        for name, value
        in required.items()
        if not value
    ]

    if missing:
        raise RuntimeError(
            "Outbound pairing completion state is incomplete: "
            + ", ".join(missing)
        )

    if algorithm != "Ed25519":
        raise RuntimeError(
            "Outbound pairing machine identity is invalid"
        )

    try:
        capability = (
            nexus_peer_pairing_credential_service
            .load_credential(
                pairing_id=
                    pairing_key,
            )
        )
    except Exception as exc:
        raise RuntimeError(
            "Outbound pairing completion capability is unavailable"
        ) from exc

    if not _text(capability):
        raise RuntimeError(
            "Outbound pairing completion capability is unavailable"
        )

    # Network call happens only after the pairing is durably completing
    # and the exact original capability has been recovered.
    response = requester(
        remote_instance_id=
            remote_instance_id,
        peer_base_url=
            peer_base_url,
        enrollment_id=
            remote_enrollment_id,
        pairing_id=
            pairing_key,
        enrollment_capability=
            capability,
        timeout=
            timeout,
    )

    if not isinstance(
        response,
        dict,
    ):
        raise RuntimeError(
            "Enrollment completion requester returned invalid response"
        )

    if (
        _text(response.get("status"))
        != "connected"
    ):
        raise RuntimeError(
            "Enrollment completion requester did not connect"
        )

    if (
        _text(
            response.get(
                "enrollmentId"
            )
        )
        != remote_enrollment_id
    ):
        raise RuntimeError(
            "Enrollment completion response enrollment mismatch"
        )

    if (
        _text(
            response.get(
                "pairingId"
            )
        )
        != pairing_key
    ):
        raise RuntimeError(
            "Enrollment completion response pairing mismatch"
        )

    if (
        _text(
            response.get(
                "localInstanceId"
            )
        )
        != remote_instance_id
    ):
        raise RuntimeError(
            "Enrollment completion response remote Nexus mismatch"
        )

    if (
        _text(
            response.get(
                "remoteInstanceId"
            )
        )
        != local_instance_id
    ):
        raise RuntimeError(
            "Enrollment completion response requester mismatch"
        )

    existing_peer = (
        nexus_peer_repository
        .get_peer_by_instances(
            local_instance_id=
                local_instance_id,
            remote_instance_id=
                remote_instance_id,
        )
    )

    created_peer = False

    if existing_peer is not None:
        if not _machine_identity_matches(
            existing_peer,
            pairing,
        ):
            raise PermissionError(
                "Existing reciprocal peer machine identity conflicts "
                "with outbound pairing"
            )

        peer_id = _text(
            existing_peer.get(
                "peer_id"
            )
        )

        if not peer_id:
            raise RuntimeError(
                "Existing reciprocal peer identity is invalid"
            )

    else:
        identity_document = (
            _safe_identity_document(
                pairing
            )
        )

        registered = (
            nexus_peer_settings_service
            .register_verified_peer(
                peer_id=(
                    "peer-"
                    + remote_instance_id
                ),
                identity_document=
                    identity_document,
                peer_base_url=
                    peer_base_url,
            )
        )

        peer = (
            registered.get("peer")
            if isinstance(
                registered,
                dict,
            )
            else None
        )

        if not isinstance(
            peer,
            dict,
        ):
            raise RuntimeError(
                "Reciprocal peer registration returned invalid state"
            )

        if (
            _text(
                peer.get(
                    "remoteInstanceId"
                )
            )
            != remote_instance_id
        ):
            raise RuntimeError(
                "Reciprocal peer registration identity mismatch"
            )

        machine = (
            peer.get(
                "machineIdentity"
            )
        )

        if not isinstance(
            machine,
            dict,
        ):
            raise RuntimeError(
                "Reciprocal peer machine identity is missing"
            )

        if (
            _text(
                machine.get(
                    "algorithm"
                )
            )
            != algorithm
            or _text(
                machine.get(
                    "publicKey"
                )
            )
            != public_key
            or _text(
                machine.get(
                    "fingerprint"
                )
            )
            != fingerprint
        ):
            raise RuntimeError(
                "Reciprocal peer machine identity mismatch"
            )

        peer_id = _text(
            peer.get(
                "peerId"
            )
        )

        if not peer_id:
            raise RuntimeError(
                "Reciprocal peer registration returned no peerId"
            )

        created_peer = True

    connected = (
        nexus_peer_outbound_pairing_repository
        .transition_pairing(
            pairing_id=
                pairing_key,
            expected_status=
                "completing",
            new_status=
                "connected",
        )
    )

    # Capability deletion is deliberately last. Any failure before the
    # connected transition remains retryable with the exact same
    # initiator-owned capability.
    (
        nexus_peer_pairing_credential_service
        .delete_credential(
            pairing_id=
                pairing_key,
        )
    )

    return {
        "status":
            "connected",
        "pairingId":
            pairing_key,
        "remoteInstanceId":
            remote_instance_id,
        "remoteEnrollmentId":
            remote_enrollment_id,
        "peerId":
            peer_id,
        "created":
            created_peer,
        "alreadyConnected":
            False,
        "connectedAt":
            connected.get(
                "connected_at"
            ),
    }
