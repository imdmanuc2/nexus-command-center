from datetime import datetime, timezone

import pytest

from backend.services import nexus_peer_pairing_request_service as service


def _public_pairing(
    *,
    status="requesting",
):
    return {
        "pairingId": "pairing-test",
        "remoteInstanceId": "nexus-remote",
        "remoteName": "Remote Nexus",
        "remoteHostname": "remote-host",
        "remotePublicKeyFingerprint":
            "sha256:remote",
        "remoteEnrollmentId": "",
        "status": status,
        "expiresAt": None,
        "requestedAt": None,
        "approvedAt": None,
        "rejectedAt": None,
        "connectedAt": None,
        "lastError": "",
        "createdAt":
            datetime(
                2026,
                9,
                1,
                tzinfo=timezone.utc,
            ),
        "updatedAt":
            datetime(
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
        "remote_public_key_algorithm":
            "Ed25519",
        "remote_public_key": "remote-key",
        "remote_public_key_fingerprint":
            "sha256:remote",
        "remote_enrollment_id":
            "enroll-test",
        "status": status,
        "expires_at":
            "2026-09-01T12:15:00Z",
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
        remote_public_key_fingerprint=
            "sha256:remote",
        local_peer_base_url="http://local:8561",
        enrollment_requester=requester,
    )


def test_happy_path_orders_state_network_credential_transition(
    monkeypatch,
):
    calls = []

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_service,
        "create_outbound_pairing",
        lambda **kwargs: (
            calls.append("create")
            or {
                "status": "ok",
                "created": True,
                "pairing": _public_pairing(),
            }
        ),
    )

    def requester(**kwargs):
        calls.append("request")

        return {
            "status": "ok",
            "enrollmentId": "enroll-test",
            "enrollmentStatus": "pending",
            "expiresAt":
                "2026-09-01T12:15:00Z",
            "enrollmentSecret":
                "temporary-test-secret",
        }

    monkeypatch.setattr(
        service.nexus_peer_pairing_credential_service,
        "store_credential",
        lambda **kwargs: (
            calls.append("store")
            or None
        ),
    )

    def transition(**kwargs):
        calls.append("transition")

        assert kwargs == {
            "pairing_id": "pairing-test",
            "expected_status": "requesting",
            "new_status": "pending",
            "remote_enrollment_id":
                "enroll-test",
            "expires_at":
                "2026-09-01T12:15:00Z",
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
        "request",
        "store",
        "transition",
    ]

    assert result["created"] is True
    assert result["pairing"]["status"] == "pending"
    assert (
        result["pairing"]["remoteEnrollmentId"]
        == "enroll-test"
    )

    assert "enrollmentSecret" not in result
    assert "peerBaseUrl" not in result


def test_existing_active_pairing_does_not_send_request(
    monkeypatch,
):
    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_service,
        "create_outbound_pairing",
        lambda **kwargs: {
            "status": "ok",
            "created": False,
            "pairing": _public_pairing(
                status="pending"
            ),
        },
    )

    def requester(**kwargs):
        raise AssertionError(
            "existing pairing must not send network request"
        )

    result = _call(
        requester=requester,
    )

    assert result["created"] is False
    assert result["pairing"]["status"] == "pending"


def test_transport_failure_marks_request_failed(
    monkeypatch,
):
    transitions = []

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_service,
        "create_outbound_pairing",
        lambda **kwargs: {
            "status": "ok",
            "created": True,
            "pairing": _public_pairing(),
        },
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

    assert transitions == [
        {
            "pairing_id": "pairing-test",
            "expected_status": "requesting",
            "new_status": "failed",
            "last_error":
                "pairing_request_failed",
        }
    ]


def test_invalid_response_marks_request_failed(
    monkeypatch,
):
    transitions = []

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_service,
        "create_outbound_pairing",
        lambda **kwargs: {
            "status": "ok",
            "created": True,
            "pairing": _public_pairing(),
        },
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

    assert transitions[-1][
        "new_status"
    ] == "failed"


def test_credential_store_failure_marks_failed(
    monkeypatch,
):
    transitions = []

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_service,
        "create_outbound_pairing",
        lambda **kwargs: {
            "status": "ok",
            "created": True,
            "pairing": _public_pairing(),
        },
    )

    monkeypatch.setattr(
        service.nexus_peer_pairing_credential_service,
        "store_credential",
        lambda **kwargs: (
            (_ for _ in ()).throw(
                RuntimeError(
                    "synthetic credential failure"
                )
            )
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
            requester=lambda **kwargs: {
                "status": "ok",
                "enrollmentId": "enroll-test",
                "enrollmentStatus": "pending",
                "expiresAt":
                    "2026-09-01T12:15:00Z",
                "enrollmentSecret":
                    "temporary-test-secret",
            },
        )

    assert transitions[-1][
        "new_status"
    ] == "failed"


def test_pending_transition_failure_deletes_credential(
    monkeypatch,
):
    calls = []

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_service,
        "create_outbound_pairing",
        lambda **kwargs: {
            "status": "ok",
            "created": True,
            "pairing": _public_pairing(),
        },
    )

    monkeypatch.setattr(
        service.nexus_peer_pairing_credential_service,
        "store_credential",
        lambda **kwargs: (
            calls.append("store")
            or None
        ),
    )

    monkeypatch.setattr(
        service.nexus_peer_pairing_credential_service,
        "delete_credential",
        lambda **kwargs: (
            calls.append("delete")
            or True
        ),
    )

    transition_count = {
        "value": 0,
    }

    def transition(**kwargs):
        transition_count["value"] += 1

        if transition_count["value"] == 1:
            calls.append("pending-fail")
            raise RuntimeError(
                "synthetic transition failure"
            )

        calls.append("mark-failed")
        return _row(
            status="failed"
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
            requester=lambda **kwargs: {
                "status": "ok",
                "enrollmentId": "enroll-test",
                "enrollmentStatus": "pending",
                "expiresAt":
                    "2026-09-01T12:15:00Z",
                "enrollmentSecret":
                    "temporary-test-secret",
            },
        )

    assert calls == [
        "store",
        "pending-fail",
        "delete",
        "mark-failed",
    ]


def test_result_never_exposes_enrollment_secret(
    monkeypatch,
):
    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_service,
        "create_outbound_pairing",
        lambda **kwargs: {
            "status": "ok",
            "created": True,
            "pairing": _public_pairing(),
        },
    )

    monkeypatch.setattr(
        service.nexus_peer_pairing_credential_service,
        "store_credential",
        lambda **kwargs: None,
    )

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_repository,
        "transition_pairing",
        lambda **kwargs: _row(),
    )

    result = _call(
        requester=lambda **kwargs: {
            "status": "ok",
            "enrollmentId": "enroll-test",
            "enrollmentStatus": "pending",
            "expiresAt":
                "2026-09-01T12:15:00Z",
            "enrollmentSecret":
                "temporary-test-secret",
        },
    )

    rendered = repr(
        result
    )

    assert (
        "temporary-test-secret"
        not in rendered
    )

    assert (
        "enrollmentSecret"
        not in rendered
    )
