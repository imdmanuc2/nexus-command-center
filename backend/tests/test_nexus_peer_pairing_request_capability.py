import hashlib

import pytest

from backend.services import (
    nexus_peer_pairing_request_service as service,
)


CAPABILITY = "initiator-owned-test-capability"


def _new_pairing():
    return {
        "status": "ok",
        "created": True,
        "pairing": {
            "pairingId": "pairing-test",
            "remoteInstanceId": "nexus-remote",
            "remoteName": "Remote Nexus",
            "remoteHostname": "remote",
            "remotePublicKeyFingerprint": "sha256:remote",
            "status": "requesting",
            "expiresAt": None,
            "requestedAt": None,
            "approvedAt": None,
            "rejectedAt": None,
            "connectedAt": None,
            "lastError": "",
            "createdAt": "created",
            "updatedAt": "updated",
        },
    }


def _request_kwargs(requester):
    return {
        "remote_instance_id": "nexus-remote",
        "remote_name": "Remote Nexus",
        "remote_hostname": "remote",
        "peer_base_url": "http://remote:8561",
        "remote_public_key_algorithm": "Ed25519",
        "remote_public_key": "remote-key",
        "remote_public_key_fingerprint": "sha256:remote",
        "local_peer_base_url": "http://local:8561",
        "enrollment_requester": requester,
    }


def test_capability_is_stored_before_network_and_only_hash_sent(
    monkeypatch,
):
    events = []

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_service,
        "create_outbound_pairing",
        lambda **kwargs: _new_pairing(),
    )

    monkeypatch.setattr(
        service.nexus_peer_pairing_credential_service,
        "generate_credential",
        lambda: CAPABILITY,
    )

    def store_credential(**kwargs):
        assert kwargs["pairing_id"] == "pairing-test"
        assert kwargs["enrollment_secret"] == CAPABILITY
        events.append("stored")

    monkeypatch.setattr(
        service.nexus_peer_pairing_credential_service,
        "store_credential",
        store_credential,
    )

    expected_hash = hashlib.sha256(
        CAPABILITY.encode("utf-8")
    ).hexdigest()

    def requester(**kwargs):
        assert events == ["stored"]
        assert kwargs["pairing_id"] == "pairing-test"
        assert kwargs["capability_hash"] == expected_hash
        assert "enrollment_secret" not in kwargs
        events.append("network")

        return {
            "status": "ok",
            "enrollmentId": "enroll-test",
            "enrollmentStatus": "pending",
            "expiresAt": "expires",
        }

    def transition(**kwargs):
        assert events == [
            "stored",
            "network",
        ]

        events.append("pending")

        return {
            "pairing_id": "pairing-test",
            "remote_instance_id": "nexus-remote",
            "remote_name": "Remote Nexus",
            "remote_hostname": "remote",
            "remote_public_key_fingerprint":
                "sha256:remote",
            "remote_enrollment_id": "enroll-test",
            "status": "pending",
            "expires_at": "expires",
            "requested_at": None,
            "approved_at": None,
            "rejected_at": None,
            "connected_at": None,
            "last_error": "",
            "created_at": "created",
            "updated_at": "updated",
        }

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_repository,
        "transition_pairing",
        transition,
    )

    result = service.request_pairing(
        **_request_kwargs(requester)
    )

    assert events == [
        "stored",
        "network",
        "pending",
    ]

    assert result["pairing"]["status"] == "pending"
    assert "enrollmentSecret" not in result
    assert CAPABILITY not in repr(result)


def test_transport_failure_preserves_requesting_and_credential(
    monkeypatch,
):
    events = []

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_service,
        "create_outbound_pairing",
        lambda **kwargs: _new_pairing(),
    )

    monkeypatch.setattr(
        service.nexus_peer_pairing_credential_service,
        "generate_credential",
        lambda: CAPABILITY,
    )

    monkeypatch.setattr(
        service.nexus_peer_pairing_credential_service,
        "store_credential",
        lambda **kwargs: events.append("stored"),
    )

    monkeypatch.setattr(
        service.nexus_peer_pairing_credential_service,
        "delete_credential",
        lambda **kwargs: events.append("deleted"),
    )

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_repository,
        "transition_pairing",
        lambda **kwargs: events.append(
            "transitioned"
        ),
    )

    def requester(**kwargs):
        events.append("network")
        raise RuntimeError("transport lost")

    with pytest.raises(
        RuntimeError,
        match="transport lost",
    ):
        service.request_pairing(
            **_request_kwargs(requester)
        )

    assert events == [
        "stored",
        "network",
    ]


def test_capability_store_failure_never_sends_network_request(
    monkeypatch,
):
    events = []

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_service,
        "create_outbound_pairing",
        lambda **kwargs: _new_pairing(),
    )

    monkeypatch.setattr(
        service.nexus_peer_pairing_credential_service,
        "generate_credential",
        lambda: CAPABILITY,
    )

    def store_credential(**kwargs):
        events.append("store")
        raise RuntimeError("credential store failed")

    monkeypatch.setattr(
        service.nexus_peer_pairing_credential_service,
        "store_credential",
        store_credential,
    )

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_repository,
        "transition_pairing",
        lambda **kwargs: events.append(
            (
                kwargs["expected_status"],
                kwargs["new_status"],
            )
        ),
    )

    def requester(**kwargs):
        raise AssertionError(
            "network request occurred before credential storage"
        )

    with pytest.raises(
        RuntimeError,
        match="credential store failed",
    ):
        service.request_pairing(
            **_request_kwargs(requester)
        )

    assert events == [
        "store",
        ("requesting", "failed"),
    ]


def test_success_response_does_not_supply_capability(
    monkeypatch,
):
    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_service,
        "create_outbound_pairing",
        lambda **kwargs: _new_pairing(),
    )

    monkeypatch.setattr(
        service.nexus_peer_pairing_credential_service,
        "generate_credential",
        lambda: CAPABILITY,
    )

    monkeypatch.setattr(
        service.nexus_peer_pairing_credential_service,
        "store_credential",
        lambda **kwargs: None,
    )

    monkeypatch.setattr(
        service.nexus_peer_pairing_credential_service,
        "delete_credential",
        lambda **kwargs: None,
    )

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_repository,
        "transition_pairing",
        lambda **kwargs: {
            "pairing_id": "pairing-test",
            "remote_instance_id": "nexus-remote",
            "remote_name": "Remote Nexus",
            "remote_hostname": "remote",
            "remote_public_key_fingerprint":
                "sha256:remote",
            "remote_enrollment_id": "enroll-test",
            "status": "pending",
            "expires_at": "expires",
            "requested_at": None,
            "approved_at": None,
            "rejected_at": None,
            "connected_at": None,
            "last_error": "",
            "created_at": "created",
            "updated_at": "updated",
        },
    )

    def requester(**kwargs):
        return {
            "status": "ok",
            "enrollmentId": "enroll-test",
            "enrollmentStatus": "pending",
            "expiresAt": "expires",
        }

    result = service.request_pairing(
        **_request_kwargs(requester)
    )

    assert "enrollmentSecret" not in repr(result)
    assert CAPABILITY not in repr(result)



def _recovery_call(*, requester):
    return service.request_pairing(
        remote_instance_id="nexus-remote",
        remote_name="Remote Nexus",
        remote_hostname="remote-host",
        peer_base_url="http://10.0.0.2:8561",
        remote_public_key_algorithm="Ed25519",
        remote_public_key="test-public-key",
        remote_public_key_fingerprint=(
            "sha256:" + ("a" * 64)
        ),
        local_peer_base_url="http://10.0.0.1:8561",
        enrollment_requester=requester,
    )

def test_existing_requesting_pairing_reuses_stored_capability(
    monkeypatch,
):
    capability = "same-recovery-capability"
    sent = []
    generated = []

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_service,
        "create_outbound_pairing",
        lambda **kwargs: {
            "status": "ok",
            "created": False,
            "pairing": _new_pairing()["pairing"],
        },
    )

    monkeypatch.setattr(
        service.nexus_peer_pairing_credential_service,
        "load_credential",
        lambda **kwargs: capability,
    )

    monkeypatch.setattr(
        service.nexus_peer_pairing_credential_service,
        "generate_credential",
        lambda: (
            generated.append(True)
            or "replacement-must-not-be-used"
        ),
    )

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_repository,
        "transition_pairing",
        lambda **kwargs: {
            "pairing_id": "pairing-test",
            "local_instance_id": "nexus-local",
            "remote_instance_id": "nexus-remote",
            "remote_name": "Remote Nexus",
            "remote_hostname": "remote",
            "peer_base_url": "http://remote:8561",
            "remote_public_key_algorithm": "Ed25519",
            "remote_public_key": "remote-key",
            "remote_public_key_fingerprint": "sha256:remote",
            "remote_enrollment_id": "enroll-retry",
            "status": "pending",
            "expires_at": "2026-09-01T12:15:00Z",
            "requested_at": None,
            "approved_at": None,
            "rejected_at": None,
            "connected_at": None,
            "last_error": "",
            "created_at": "created",
            "updated_at": "updated",
        },
    )

    def requester(**kwargs):
        sent.append(kwargs)

        return {
            "status": "ok",
            "enrollmentId": "enroll-retry",
            "enrollmentStatus": "pending",
            "expiresAt": "2026-09-01T12:15:00Z",
        }

    result = _recovery_call(
        requester=requester,
    )

    assert generated == []
    assert len(sent) == 1

    assert (
        sent[0]["pairing_id"]
        == "pairing-test"
    )

    assert sent[0]["capability_hash"] == (
        hashlib.sha256(
            capability.encode("utf-8")
        ).hexdigest()
    )

    assert result["created"] is False
    assert result["pairing"]["status"] == "pending"


def test_existing_requesting_pairing_missing_capability_fails_closed(
    monkeypatch,
):
    network = []
    generated = []

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_service,
        "create_outbound_pairing",
        lambda **kwargs: {
            "status": "ok",
            "created": False,
            "pairing": _new_pairing()["pairing"],
        },
    )

    def missing(**kwargs):
        raise FileNotFoundError(
            "synthetic missing capability"
        )

    monkeypatch.setattr(
        service.nexus_peer_pairing_credential_service,
        "load_credential",
        missing,
    )

    monkeypatch.setattr(
        service.nexus_peer_pairing_credential_service,
        "generate_credential",
        lambda: (
            generated.append(True)
            or "must-not-generate"
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="capability is unavailable",
    ):
        _recovery_call(
            requester=lambda **kwargs: (
                network.append(kwargs)
                or {}
            ),
        )

    assert generated == []
    assert network == []


def test_retry_transport_failure_keeps_same_recovery_state(
    monkeypatch,
):
    capability = "same-recovery-capability"
    sent = []

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_service,
        "create_outbound_pairing",
        lambda **kwargs: {
            "status": "ok",
            "created": False,
            "pairing": _new_pairing()["pairing"],
        },
    )

    monkeypatch.setattr(
        service.nexus_peer_pairing_credential_service,
        "load_credential",
        lambda **kwargs: capability,
    )

    def requester(**kwargs):
        sent.append(kwargs)

        raise RuntimeError(
            "synthetic second transport failure"
        )

    with pytest.raises(
        RuntimeError,
        match="synthetic second transport failure",
    ):
        _recovery_call(
            requester=requester,
        )

    assert len(sent) == 1
    assert (
        sent[0]["pairing_id"]
        == "pairing-test"
    )
    assert sent[0]["capability_hash"] == (
        hashlib.sha256(
            capability.encode("utf-8")
        ).hexdigest()
    )

def test_pending_transition_failure_preserves_recovery_capability(
    monkeypatch,
):
    capability = "transition-recovery-capability"
    deleted = []
    failed = []
    sent = []

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_service,
        "create_outbound_pairing",
        lambda **kwargs: {
            "status": "ok",
            "created": False,
            "pairing": _new_pairing()["pairing"],
        },
    )

    monkeypatch.setattr(
        service.nexus_peer_pairing_credential_service,
        "load_credential",
        lambda **kwargs: capability,
    )

    monkeypatch.setattr(
        service.nexus_peer_pairing_credential_service,
        "delete_credential",
        lambda **kwargs: deleted.append(kwargs),
    )

    monkeypatch.setattr(
        service,
        "_fail_requesting_pairing",
        lambda pairing_id: failed.append(pairing_id),
    )

    def transition(**kwargs):
        raise RuntimeError(
            "synthetic pending transition failure"
        )

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_repository,
        "transition_pairing",
        transition,
    )

    def requester(**kwargs):
        sent.append(kwargs)

        return {
            "status": "ok",
            "enrollmentId": "enroll-transition-retry",
            "enrollmentStatus": "pending",
            "expiresAt": "2026-09-01T12:15:00Z",
        }

    with pytest.raises(
        RuntimeError,
        match="synthetic pending transition failure",
    ):
        _recovery_call(
            requester=requester,
        )

    assert len(sent) == 1

    assert sent[0]["pairing_id"] == "pairing-test"

    assert sent[0]["capability_hash"] == (
        hashlib.sha256(
            capability.encode("utf-8")
        ).hexdigest()
    )

    assert deleted == []
    assert failed == []
