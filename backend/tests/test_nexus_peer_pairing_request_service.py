from datetime import datetime, timezone
import hashlib

import pytest

from backend.services import (
    nexus_peer_pairing_request_service as service,
)


CAPABILITY = "synthetic-initiator-capability"


def _public_pairing(
    *,
    status="requesting",
):
    return {
        "pairingId": "pairing-test",
        "remoteInstanceId": "nexus-remote",
        "remoteName": "Remote Nexus",
        "remoteHostname": "remote-host",
        "remotePublicKeyFingerprint": "sha256:remote",
        "remoteEnrollmentId": "",
        "status": status,
        "expiresAt": None,
        "requestedAt": None,
        "approvedAt": None,
        "rejectedAt": None,
        "connectedAt": None,
        "lastError": "",
        "createdAt": datetime(
            2026,
            9,
            1,
            tzinfo=timezone.utc,
        ),
        "updatedAt": datetime(
            2026,
            9,
            1,
            tzinfo=timezone.utc,
        ),
    }


def _row(
    *,
    status="pending",
):
    now = datetime(
        2026,
        9,
        1,
        tzinfo=timezone.utc,
    )

    return {
        "pairing_id": "pairing-test",
        "local_instance_id": "nexus-local",
        "remote_instance_id": "nexus-remote",
        "remote_name": "Remote Nexus",
        "remote_hostname": "remote-host",
        "peer_base_url": "http://remote:8561",
        "remote_public_key_algorithm": "Ed25519",
        "remote_public_key": "remote-key",
        "remote_public_key_fingerprint": "sha256:remote",
        "remote_enrollment_id": "enroll-test",
        "status": status,
        "expires_at": "2026-09-01T12:15:00Z",
        "requested_at": now,
        "approved_at": None,
        "rejected_at": None,
        "connected_at": None,
        "last_error": "",
        "created_at": now,
        "updated_at": now,
    }


def _call(
    *,
    requester,
):
    return service.request_pairing(
        remote_instance_id="nexus-remote",
        remote_name="Remote Nexus",
        remote_hostname="remote-host",
        peer_base_url="http://remote:8561",
        remote_public_key_algorithm="Ed25519",
        remote_public_key="remote-key",
        remote_public_key_fingerprint="sha256:remote",
        local_peer_base_url="http://local:8561",
        enrollment_requester=requester,
    )


def _mock_new_capability(
    monkeypatch,
    *,
    calls=None,
    store_error=None,
):
    monkeypatch.setattr(
        service.nexus_peer_pairing_credential_service,
        "generate_credential",
        lambda: CAPABILITY,
    )

    def store(**kwargs):
        if calls is not None:
            calls.append("store")

        assert kwargs["pairing_id"] == "pairing-test"
        assert kwargs["enrollment_secret"] == CAPABILITY

        if store_error is not None:
            raise store_error

    monkeypatch.setattr(
        service.nexus_peer_pairing_credential_service,
        "store_credential",
        store,
    )


def _new_pairing_service_mock(
    monkeypatch,
    *,
    status="requesting",
    calls=None,
):
    def create(**kwargs):
        if calls is not None:
            calls.append("create")

        return {
            "status": "ok",
            "created": True,
            "pairing": _public_pairing(
                status=status,
            ),
        }

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_service,
        "create_outbound_pairing",
        create,
    )


def _pending_response():
    return {
        "status": "ok",
        "enrollmentId": "enroll-test",
        "enrollmentStatus": "pending",
        "expiresAt": "2026-09-01T12:15:00Z",
    }


def test_happy_path_orders_state_credential_network_transition(
    monkeypatch,
):
    calls = []

    _new_pairing_service_mock(
        monkeypatch,
        calls=calls,
    )

    _mock_new_capability(
        monkeypatch,
        calls=calls,
    )

    def requester(**kwargs):
        calls.append("request")

        assert kwargs["pairing_id"] == "pairing-test"
        assert kwargs["capability_hash"] == hashlib.sha256(
            CAPABILITY.encode("utf-8")
        ).hexdigest()

        return _pending_response()

    def transition(**kwargs):
        calls.append("transition")

        assert kwargs == {
            "pairing_id": "pairing-test",
            "expected_status": "requesting",
            "new_status": "pending",
            "remote_enrollment_id": "enroll-test",
            "expires_at": "2026-09-01T12:15:00Z",
        }

        return _row()

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_repository,
        "transition_pairing",
        transition,
    )

    result = _call(
        requester=requester,
    )

    assert calls == [
        "create",
        "store",
        "request",
        "transition",
    ]

    assert result["created"] is True
    assert result["pairing"]["status"] == "pending"
    assert (
        result["pairing"]["remoteEnrollmentId"]
        == "enroll-test"
    )


def test_existing_nonrequesting_pairing_does_not_send_request(
    monkeypatch,
):
    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_service,
        "create_outbound_pairing",
        lambda **kwargs: {
            "status": "ok",
            "created": False,
            "pairing": _public_pairing(
                status="pending",
            ),
        },
    )

    monkeypatch.setattr(
        service.nexus_peer_pairing_credential_service,
        "generate_credential",
        lambda: (_ for _ in ()).throw(
            AssertionError(
                "existing pending pairing must not generate capability"
            )
        ),
    )

    monkeypatch.setattr(
        service.nexus_peer_pairing_credential_service,
        "load_credential",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError(
                "existing pending pairing must not load capability"
            )
        ),
    )

    def requester(**kwargs):
        raise AssertionError(
            "existing pending pairing must not send network request"
        )

    result = _call(
        requester=requester,
    )

    assert result["created"] is False
    assert result["pairing"]["status"] == "pending"


def test_transport_failure_preserves_requesting_recovery(
    monkeypatch,
):
    transitions = []

    _new_pairing_service_mock(
        monkeypatch,
    )

    _mock_new_capability(
        monkeypatch,
    )

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_repository,
        "transition_pairing",
        lambda **kwargs: (
            transitions.append(kwargs)
            or _row(
                status=kwargs["new_status"]
            )
        ),
    )

    def requester(**kwargs):
        raise RuntimeError(
            "synthetic transport failure"
        )

    with pytest.raises(
        RuntimeError,
        match="synthetic transport failure",
    ):
        _call(
            requester=requester,
        )

    assert transitions == []


def test_invalid_response_preserves_requesting_recovery(
    monkeypatch,
):
    transitions = []

    _new_pairing_service_mock(
        monkeypatch,
    )

    _mock_new_capability(
        monkeypatch,
    )

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_repository,
        "transition_pairing",
        lambda **kwargs: (
            transitions.append(kwargs)
            or _row(
                status=kwargs["new_status"]
            )
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="incomplete response",
    ):
        _call(
            requester=lambda **kwargs: {
                "status": "ok",
                "enrollmentId": "enroll-test",
                "enrollmentStatus": "pending",
            },
        )

    assert transitions == []


def test_credential_store_failure_marks_failed_before_network(
    monkeypatch,
):
    transitions = []
    network = []

    _new_pairing_service_mock(
        monkeypatch,
    )

    _mock_new_capability(
        monkeypatch,
        store_error=RuntimeError(
            "synthetic credential failure"
        ),
    )

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_repository,
        "transition_pairing",
        lambda **kwargs: (
            transitions.append(kwargs)
            or _row(
                status=kwargs["new_status"]
            )
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="synthetic credential failure",
    ):
        _call(
            requester=lambda **kwargs: (
                network.append(kwargs)
                or _pending_response()
            ),
        )

    assert network == []

    assert transitions == [
        {
            "pairing_id": "pairing-test",
            "expected_status": "requesting",
            "new_status": "failed",
            "last_error": "pairing_request_failed",
        }
    ]


def test_pending_transition_failure_preserves_credential(
    monkeypatch,
):
    calls = []

    _new_pairing_service_mock(
        monkeypatch,
    )

    _mock_new_capability(
        monkeypatch,
        calls=calls,
    )

    monkeypatch.setattr(
        service.nexus_peer_pairing_credential_service,
        "delete_credential",
        lambda **kwargs: calls.append("delete"),
    )

    def transition(**kwargs):
        calls.append("pending-fail")

        raise RuntimeError(
            "synthetic transition failure"
        )

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_repository,
        "transition_pairing",
        transition,
    )

    with pytest.raises(
        RuntimeError,
        match="synthetic transition failure",
    ):
        _call(
            requester=lambda **kwargs: _pending_response(),
        )

    assert calls == [
        "store",
        "pending-fail",
    ]


def test_result_never_exposes_capability(
    monkeypatch,
):
    _new_pairing_service_mock(
        monkeypatch,
    )

    _mock_new_capability(
        monkeypatch,
    )

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_repository,
        "transition_pairing",
        lambda **kwargs: _row(),
    )

    result = _call(
        requester=lambda **kwargs: _pending_response(),
    )

    rendered = repr(result)

    assert CAPABILITY not in rendered
    assert "capabilityHash" not in rendered
    assert "capability_hash" not in rendered
