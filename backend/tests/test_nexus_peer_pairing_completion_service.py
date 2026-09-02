"""Tests for initiator-side Nexus completion orchestration."""

from unittest.mock import Mock

import pytest

from backend.services import (
    nexus_peer_pairing_completion_service
    as service,
)


PAIRING_ID = "pairing-test"
LOCAL = "nexus-local"
REMOTE = "nexus-remote"
ENROLLMENT = "enroll-remote"
CAPABILITY = "synthetic-one-time-capability"


def _pairing(
    *,
    status="approved",
):
    return {
        "pairing_id":
            PAIRING_ID,
        "local_instance_id":
            LOCAL,
        "remote_instance_id":
            REMOTE,
        "remote_name":
            "Remote Nexus",
        "remote_hostname":
            "remote-host",
        "peer_base_url":
            "http://remote.example:8561",
        "remote_public_key_algorithm":
            "Ed25519",
        "remote_public_key":
            "remote-public-key",
        "remote_public_key_fingerprint":
            "sha256:remote-fingerprint",
        "remote_enrollment_id":
            ENROLLMENT,
        "status":
            status,
        "connected_at":
            None,
    }


def _completion_response():
    return {
        "status":
            "connected",
        "enrollmentId":
            ENROLLMENT,
        "pairingId":
            PAIRING_ID,
        "localInstanceId":
            REMOTE,
        "remoteInstanceId":
            LOCAL,
        "peerId":
            "peer-" + LOCAL,
        "created":
            True,
    }


def _registered_peer():
    return {
        "status": "ok",
        "peer": {
            "peerId":
                "peer-" + REMOTE,
            "remoteInstanceId":
                REMOTE,
            "machineIdentity": {
                "algorithm":
                    "Ed25519",
                "publicKey":
                    "remote-public-key",
                "fingerprint":
                    "sha256:remote-fingerprint",
            },
        },
    }


def _existing_peer(**changes):
    row = {
        "peer_id":
            "peer-" + REMOTE,
        "local_instance_id":
            LOCAL,
        "remote_instance_id":
            REMOTE,
        "public_key_algorithm":
            "Ed25519",
        "public_key":
            "remote-public-key",
        "public_key_fingerprint":
            "sha256:remote-fingerprint",
        "name":
            "User Renamed Peer",
        "peer_base_url":
            "http://changed.example:8561",
        "enabled":
            False,
        "management_enabled":
            True,
    }

    row.update(changes)
    return row


def _install(
    monkeypatch,
    *,
    initial_status="approved",
    existing_peer=None,
    requester=None,
):
    initial = _pairing(
        status=initial_status
    )

    completing = {
        **initial,
        "status": "completing",
    }

    connected = {
        **completing,
        "status": "connected",
        "connected_at": "connected-time",
    }

    monkeypatch.setattr(
        service
        .nexus_peer_outbound_pairing_repository,
        "get_pairing",
        Mock(
            return_value=initial
        ),
    )

    transitions = []

    def transition_pairing(**kwargs):
        transitions.append(
            kwargs
        )

        if (
            kwargs["new_status"]
            == "completing"
        ):
            return completing

        if (
            kwargs["new_status"]
            == "connected"
        ):
            return connected

        raise AssertionError(
            "unexpected transition"
        )

    monkeypatch.setattr(
        service
        .nexus_peer_outbound_pairing_repository,
        "transition_pairing",
        transition_pairing,
    )

    monkeypatch.setattr(
        service
        .nexus_peer_pairing_credential_service,
        "load_credential",
        Mock(
            return_value=CAPABILITY
        ),
    )

    delete = Mock(
        return_value=True
    )

    monkeypatch.setattr(
        service
        .nexus_peer_pairing_credential_service,
        "delete_credential",
        delete,
    )

    monkeypatch.setattr(
        service
        .nexus_peer_repository,
        "get_peer_by_instances",
        Mock(
            return_value=existing_peer
        ),
    )

    register = Mock(
        return_value=
            _registered_peer()
    )

    monkeypatch.setattr(
        service
        .nexus_peer_settings_service,
        "register_verified_peer",
        register,
    )

    requester_mock = (
        requester
        if requester is not None
        else Mock(
            return_value=
                _completion_response()
        )
    )

    return (
        transitions,
        delete,
        register,
        requester_mock,
    )


def test_approved_completion_order_and_cleanup(
    monkeypatch,
):
    events = []

    initial = _pairing(
        status="approved"
    )

    completing = {
        **initial,
        "status": "completing",
    }

    connected = {
        **completing,
        "status": "connected",
        "connected_at": "done",
    }

    monkeypatch.setattr(
        service
        .nexus_peer_outbound_pairing_repository,
        "get_pairing",
        lambda pairing_id:
            initial,
    )

    def transition(**kwargs):
        events.append(
            "transition:"
            + kwargs["new_status"]
        )

        return (
            completing
            if kwargs["new_status"]
            == "completing"
            else connected
        )

    monkeypatch.setattr(
        service
        .nexus_peer_outbound_pairing_repository,
        "transition_pairing",
        transition,
    )

    monkeypatch.setattr(
        service
        .nexus_peer_pairing_credential_service,
        "load_credential",
        lambda **kwargs:
            events.append("load")
            or CAPABILITY,
    )

    monkeypatch.setattr(
        service
        .nexus_peer_repository,
        "get_peer_by_instances",
        lambda **kwargs:
            events.append("peer-read")
            or None,
    )

    monkeypatch.setattr(
        service
        .nexus_peer_settings_service,
        "register_verified_peer",
        lambda **kwargs:
            events.append("peer-create")
            or _registered_peer(),
    )

    monkeypatch.setattr(
        service
        .nexus_peer_pairing_credential_service,
        "delete_credential",
        lambda **kwargs:
            events.append("delete")
            or True,
    )

    def requester(**kwargs):
        events.append("network")
        return _completion_response()

    result = service.complete_pairing(
        pairing_id=PAIRING_ID,
        completion_requester=requester,
    )

    assert result["status"] == "connected"

    assert events == [
        "transition:completing",
        "load",
        "network",
        "peer-read",
        "peer-create",
        "transition:connected",
        "delete",
    ]


def test_completion_reuses_stored_capability(
    monkeypatch,
):
    (
        transitions,
        delete,
        register,
        requester,
    ) = _install(
        monkeypatch
    )

    service.complete_pairing(
        pairing_id=PAIRING_ID,
        completion_requester=requester,
    )

    requester.assert_called_once()

    assert (
        requester.call_args.kwargs[
            "enrollment_capability"
        ]
        == CAPABILITY
    )

    assert delete.call_count == 1


def test_completing_retry_does_not_repeat_state_transition(
    monkeypatch,
):
    (
        transitions,
        delete,
        register,
        requester,
    ) = _install(
        monkeypatch,
        initial_status="completing",
    )

    service.complete_pairing(
        pairing_id=PAIRING_ID,
        completion_requester=requester,
    )

    assert [
        call["new_status"]
        for call in transitions
    ] == [
        "connected",
    ]

    assert delete.call_count == 1


def test_existing_exact_peer_is_preserved(
    monkeypatch,
):
    existing = _existing_peer()

    (
        transitions,
        delete,
        register,
        requester,
    ) = _install(
        monkeypatch,
        existing_peer=existing,
    )

    result = service.complete_pairing(
        pairing_id=PAIRING_ID,
        completion_requester=requester,
    )

    register.assert_not_called()

    assert (
        result["peerId"]
        == existing["peer_id"]
    )

    assert result["created"] is False

    assert delete.call_count == 1


def test_existing_peer_machine_conflict_fails_before_connected(
    monkeypatch,
):
    (
        transitions,
        delete,
        register,
        requester,
    ) = _install(
        monkeypatch,
        existing_peer=
            _existing_peer(
                public_key=
                    "attacker-key"
            ),
    )

    with pytest.raises(
        PermissionError,
        match="machine identity conflicts",
    ):
        service.complete_pairing(
            pairing_id=PAIRING_ID,
            completion_requester=requester,
        )

    assert (
        "connected"
        not in [
            call["new_status"]
            for call in transitions
        ]
    )

    delete.assert_not_called()
    register.assert_not_called()


def test_transport_failure_preserves_completing_and_capability(
    monkeypatch,
):
    requester = Mock(
        side_effect=RuntimeError(
            "synthetic transport failure"
        )
    )

    (
        transitions,
        delete,
        register,
        _,
    ) = _install(
        monkeypatch,
        requester=requester,
    )

    with pytest.raises(
        RuntimeError,
        match="synthetic transport failure",
    ):
        service.complete_pairing(
            pairing_id=PAIRING_ID,
            completion_requester=requester,
        )

    assert [
        call["new_status"]
        for call in transitions
    ] == [
        "completing",
    ]

    delete.assert_not_called()
    register.assert_not_called()


def test_peer_registration_failure_preserves_capability(
    monkeypatch,
):
    (
        transitions,
        delete,
        register,
        requester,
    ) = _install(
        monkeypatch
    )

    register.side_effect = RuntimeError(
        "synthetic peer write failure"
    )

    with pytest.raises(
        RuntimeError,
        match="synthetic peer write failure",
    ):
        service.complete_pairing(
            pairing_id=PAIRING_ID,
            completion_requester=requester,
        )

    assert (
        "connected"
        not in [
            call["new_status"]
            for call in transitions
        ]
    )

    delete.assert_not_called()


def test_connected_transition_failure_preserves_capability(
    monkeypatch,
):
    initial = _pairing(
        status="completing"
    )

    monkeypatch.setattr(
        service
        .nexus_peer_outbound_pairing_repository,
        "get_pairing",
        Mock(
            return_value=initial
        ),
    )

    monkeypatch.setattr(
        service
        .nexus_peer_pairing_credential_service,
        "load_credential",
        Mock(
            return_value=CAPABILITY
        ),
    )

    monkeypatch.setattr(
        service
        .nexus_peer_repository,
        "get_peer_by_instances",
        Mock(
            return_value=
                _existing_peer()
        ),
    )

    monkeypatch.setattr(
        service
        .nexus_peer_outbound_pairing_repository,
        "transition_pairing",
        Mock(
            side_effect=RuntimeError(
                "synthetic transition failure"
            )
        ),
    )

    delete = Mock()

    monkeypatch.setattr(
        service
        .nexus_peer_pairing_credential_service,
        "delete_credential",
        delete,
    )

    with pytest.raises(
        RuntimeError,
        match="synthetic transition failure",
    ):
        service.complete_pairing(
            pairing_id=PAIRING_ID,
            completion_requester=lambda **kwargs:
                _completion_response(),
        )

    delete.assert_not_called()


def test_not_approved_state_does_not_load_capability(
    monkeypatch,
):
    monkeypatch.setattr(
        service
        .nexus_peer_outbound_pairing_repository,
        "get_pairing",
        Mock(
            return_value=
                _pairing(
                    status="pending"
                )
        ),
    )

    load = Mock()

    monkeypatch.setattr(
        service
        .nexus_peer_pairing_credential_service,
        "load_credential",
        load,
    )

    with pytest.raises(
        PermissionError,
        match="not approved",
    ):
        service.complete_pairing(
            pairing_id=PAIRING_ID,
        )

    load.assert_not_called()


def test_connected_state_is_idempotent_and_no_network(
    monkeypatch,
):
    connected = {
        **_pairing(
            status="connected"
        ),
        "connected_at":
            "already-connected",
    }

    monkeypatch.setattr(
        service
        .nexus_peer_outbound_pairing_repository,
        "get_pairing",
        Mock(
            return_value=connected
        ),
    )

    requester = Mock()

    result = service.complete_pairing(
        pairing_id=PAIRING_ID,
        completion_requester=requester,
    )

    assert (
        result["alreadyConnected"]
        is True
    )

    requester.assert_not_called()
