"""Isolated tests for identity-bound receiver completion service."""

import hashlib
from unittest.mock import patch

import pytest

from backend.services import (
    nexus_peer_enrollment_service
    as service,
)


CAPABILITY = (
    "synthetic-one-time-capability"
)
PAIRING_ID = "pairing-test"
REMOTE_ID = "nexus-remote"


def _enrollment(**changes):
    row = {
        "enrollment_id":
            "enroll-test",
        "local_instance_id":
            "nexus-local",
        "request_id":
            PAIRING_ID,
        "requested_remote_instance_id":
            REMOTE_ID,
        "requested_public_key_algorithm":
            "Ed25519",
        "requested_public_key":
            "public-key",
        "requested_public_key_fingerprint":
            "sha256:fingerprint",
        "status":
            "used",
    }

    row.update(changes)
    return row


def _peer(**changes):
    row = {
        "peer_id":
            "peer-nexus-remote",
        "local_instance_id":
            "nexus-local",
        "remote_instance_id":
            REMOTE_ID,
        "public_key_algorithm":
            "Ed25519",
        "public_key":
            "public-key",
        "public_key_fingerprint":
            "sha256:fingerprint",
        "status":
            "offline",
        "enabled":
            False,
        "peer_awareness":
            False,
        "management_enabled":
            True,
    }

    row.update(changes)
    return row


def _result(
    *,
    created=True,
    enrollment=None,
    peer=None,
):
    return {
        "created":
            created,
        "enrollment":
            enrollment
            if enrollment is not None
            else _enrollment(),
        "peer":
            peer
            if peer is not None
            else _peer(),
    }


def _complete(result):
    with patch.object(
        service,
        "_require_connections_enabled",
        return_value={
            "allow_peer_connections":
                True,
        },
    ), patch.object(
        service
        .nexus_peer_enrollment_repository,
        "complete_enrollment_atomic",
        return_value=result,
    ) as complete:
        response = (
            service
            .complete_remote_enrollment(
                enrollment_id=
                    "enroll-test",
                pairing_id=
                    PAIRING_ID,
                authenticated_remote_instance_id=
                    REMOTE_ID,
                enrollment_secret=
                    CAPABILITY,
            )
        )

    return response, complete


def test_service_forwards_all_identity_bindings():
    response, complete = _complete(
        _result()
    )

    digest = hashlib.sha256(
        CAPABILITY.encode("utf-8")
    ).hexdigest()

    complete.assert_called_once_with(
        enrollment_id=
            "enroll-test",
        pairing_id=
            PAIRING_ID,
        authenticated_remote_instance_id=
            REMOTE_ID,
        supplied_secret_hash=
            digest,
    )

    assert response == {
        "status":
            "connected",
        "enrollmentId":
            "enroll-test",
        "pairingId":
            PAIRING_ID,
        "localInstanceId":
            "nexus-local",
        "remoteInstanceId":
            REMOTE_ID,
        "peerId":
            "peer-nexus-remote",
        "created":
            True,
    }


def test_retry_allows_mutable_peer_state():
    response, _ = _complete(
        _result(
            created=False
        )
    )

    assert (
        response["status"]
        == "connected"
    )
    assert (
        response["created"]
        is False
    )


def test_pairing_result_mismatch_fails_closed():
    with pytest.raises(
        RuntimeError,
        match="pairing identity mismatch",
    ):
        _complete(
            _result(
                enrollment=_enrollment(
                    request_id=
                        "pairing-other"
                )
            )
        )


def test_authenticated_remote_result_mismatch_fails_closed():
    with pytest.raises(
        RuntimeError,
        match="authenticated remote identity mismatch",
    ):
        _complete(
            _result(
                enrollment=_enrollment(
                    requested_remote_instance_id=
                        "nexus-other"
                )
            )
        )


def test_peer_machine_identity_mismatch_fails_closed():
    with pytest.raises(
        RuntimeError,
        match="peer machine identity mismatch",
    ):
        _complete(
            _result(
                peer=_peer(
                    public_key=
                        "other-key"
                )
            )
        )


def test_empty_pairing_id_fails_before_repository():
    with patch.object(
        service,
        "_require_connections_enabled",
        return_value={
            "allow_peer_connections":
                True,
        },
    ), patch.object(
        service
        .nexus_peer_enrollment_repository,
        "complete_enrollment_atomic",
    ) as complete:
        with pytest.raises(
            ValueError,
            match="pairing_id",
        ):
            service.complete_remote_enrollment(
                enrollment_id=
                    "enroll-test",
                pairing_id="",
                authenticated_remote_instance_id=
                    REMOTE_ID,
                enrollment_secret=
                    CAPABILITY,
            )

    complete.assert_not_called()


def test_empty_authenticated_remote_fails_before_repository():
    with patch.object(
        service,
        "_require_connections_enabled",
        return_value={
            "allow_peer_connections":
                True,
        },
    ), patch.object(
        service
        .nexus_peer_enrollment_repository,
        "complete_enrollment_atomic",
    ) as complete:
        with pytest.raises(
            PermissionError,
            match="Authenticated remote instance",
        ):
            service.complete_remote_enrollment(
                enrollment_id=
                    "enroll-test",
                pairing_id=
                    PAIRING_ID,
                authenticated_remote_instance_id=
                    "",
                enrollment_secret=
                    CAPABILITY,
            )

    complete.assert_not_called()


def test_empty_capability_fails_before_repository():
    with patch.object(
        service,
        "_require_connections_enabled",
        return_value={
            "allow_peer_connections":
                True,
        },
    ), patch.object(
        service
        .nexus_peer_enrollment_repository,
        "complete_enrollment_atomic",
    ) as complete:
        with pytest.raises(
            PermissionError,
            match="capability is required",
        ):
            service.complete_remote_enrollment(
                enrollment_id=
                    "enroll-test",
                pairing_id=
                    PAIRING_ID,
                authenticated_remote_instance_id=
                    REMOTE_ID,
                enrollment_secret="",
            )

    complete.assert_not_called()


def test_connections_gate_still_required():
    with patch.object(
        service,
        "_require_connections_enabled",
        side_effect=PermissionError(
            "Nexus peer connections are disabled"
        ),
    ), patch.object(
        service
        .nexus_peer_enrollment_repository,
        "complete_enrollment_atomic",
    ) as complete:
        with pytest.raises(
            PermissionError,
            match="connections are disabled",
        ):
            service.complete_remote_enrollment(
                enrollment_id=
                    "enroll-test",
                pairing_id=
                    PAIRING_ID,
                authenticated_remote_instance_id=
                    REMOTE_ID,
                enrollment_secret=
                    CAPABILITY,
            )

    complete.assert_not_called()
