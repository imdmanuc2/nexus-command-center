"""Atomic receiver-side Nexus pairing request tests."""

import pytest

from backend.services import (
    nexus_peer_enrollment_service as enrollment,
)


def _machine_identity():
    return {
        "algorithm": "Ed25519",
        "publicKey": "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8",
        "fingerprint": "sha256:630dcd2966c4336691125448bbb25b4ff412a49c732db2c8abc1b8581bd710dd",
    }


def _peer_settings():
    return {
        "instance_id": "nexus-local",
        "allow_peer_connections": True,
    }


def _request_kwargs(
    *,
    pairing_id,
    capability_hash="a" * 64,
):
    identity = _machine_identity()

    return {
        "remote_instance_id": "nexus-remote",
        "remote_name": "Remote Nexus",
        "remote_hostname": "remote",
        "peer_base_url": "http://192.0.2.10:8561",
        "pairing_id": pairing_id,
        "capability_hash": capability_hash,
        "public_key_algorithm": identity["algorithm"],
        "public_key": identity["publicKey"],
        "public_key_fingerprint": identity["fingerprint"],
    }


def _row_from_kwargs(kwargs):
    return {
        "enrollment_id": kwargs["enrollment_id"],
        "local_instance_id": kwargs["local_instance_id"],
        "secret_hash": kwargs["secret_hash"],
        "status": "pending",
        "requested_remote_instance_id":
            kwargs["requested_remote_instance_id"],
        "requested_remote_name":
            kwargs["requested_remote_name"],
        "requested_remote_hostname":
            kwargs["requested_remote_hostname"],
        "requested_peer_base_url":
            kwargs["requested_peer_base_url"],
        "requested_public_key_algorithm":
            kwargs["requested_public_key_algorithm"],
        "requested_public_key":
            kwargs["requested_public_key"],
        "requested_public_key_fingerprint":
            kwargs[
                "requested_public_key_fingerprint"
            ],
        "request_id": kwargs["request_id"],
        "expires_at": kwargs["expires_at"],
        "approved_at": None,
        "rejected_at": None,
        "used_at": None,
        "created_at": None,
        "updated_at": None,
    }


def _mock_settings(monkeypatch):
    monkeypatch.setattr(
        enrollment,
        "_require_connections_enabled",
        lambda: _peer_settings(),
    )


def test_atomic_receiver_create_reports_created(
    monkeypatch,
):
    _mock_settings(monkeypatch)
    captured = {}

    def atomic_create(**kwargs):
        captured.update(kwargs)
        return _row_from_kwargs(kwargs)

    monkeypatch.setattr(
        enrollment.nexus_peer_enrollment_repository,
        "create_enrollment_idempotent",
        atomic_create,
    )

    result = enrollment.create_remote_pairing_request(
        **_request_kwargs(
            pairing_id="pairing-atomic-created",
        )
    )

    assert result["status"] == "ok"
    assert result["created"] is True
    assert (
        captured["request_id"]
        == "pairing-atomic-created"
    )
    assert captured["secret_hash"] == ("a" * 64)


def test_atomic_receiver_exact_retry_returns_winner(
    monkeypatch,
):
    _mock_settings(monkeypatch)

    winner = None

    def atomic_create(**kwargs):
        nonlocal winner

        if winner is None:
            winner = _row_from_kwargs(kwargs)

        return dict(winner)

    monkeypatch.setattr(
        enrollment.nexus_peer_enrollment_repository,
        "create_enrollment_idempotent",
        atomic_create,
    )

    request = _request_kwargs(
        pairing_id="pairing-atomic-retry",
    )

    first = enrollment.create_remote_pairing_request(
        **request
    )
    second = enrollment.create_remote_pairing_request(
        **request
    )

    assert first["created"] is True
    assert second["created"] is False

    assert (
        first["enrollment"]["enrollmentId"]
        == second["enrollment"]["enrollmentId"]
    )


def test_atomic_receiver_conflicting_retry_fails_closed(
    monkeypatch,
):
    _mock_settings(monkeypatch)

    winner = None

    def atomic_create(**kwargs):
        nonlocal winner

        if winner is None:
            winner = _row_from_kwargs(kwargs)

        return dict(winner)

    monkeypatch.setattr(
        enrollment.nexus_peer_enrollment_repository,
        "create_enrollment_idempotent",
        atomic_create,
    )

    enrollment.create_remote_pairing_request(
        **_request_kwargs(
            pairing_id="pairing-atomic-conflict",
            capability_hash="a" * 64,
        )
    )

    with pytest.raises(
        PermissionError,
        match="conflicts",
    ):
        enrollment.create_remote_pairing_request(
            **_request_kwargs(
                pairing_id="pairing-atomic-conflict",
                capability_hash="c" * 64,
            )
        )
