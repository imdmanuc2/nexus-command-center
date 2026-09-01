from backend.services import (
    nexus_peer_outbound_pairing_service as service,
)


REMOTE_KEY = (
    "w7T47daAc9cV3y8m8S6szSjCBGOi96MeN1OYB8DBZps"
)

REMOTE_FINGERPRINT = (
    "sha256:"
    "2680cfcad760a889b1d1f436250230c10f4ed70111943214"
    "eb49fa363a60835f"
)


def _row():
    return {
        "pairing_id": "pairing-test",
        "local_instance_id": "nexus-local",
        "remote_instance_id": "nexus-remote",
        "remote_name": "Remote Nexus",
        "remote_hostname": "remote",
        "peer_base_url": "http://remote:8561",
        "remote_public_key_algorithm": "Ed25519",
        "remote_public_key": REMOTE_KEY,
        "remote_public_key_fingerprint": REMOTE_FINGERPRINT,
        "remote_enrollment_id": None,
        "status": "requesting",
        "expires_at": None,
        "requested_at": None,
        "approved_at": None,
        "rejected_at": None,
        "connected_at": None,
        "last_error": "",
        "created_at": "2026-09-01T00:00:00+00:00",
        "updated_at": "2026-09-01T00:00:00+00:00",
    }


def test_create_outbound_pairing_is_local_state_only(monkeypatch):
    monkeypatch.setattr(
        service,
        "_local_instance_id",
        lambda: "nexus-local",
    )

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_repository,
        "get_active_pairing_for_remote",
        lambda **kwargs: None,
    )

    captured = {}

    def create_pairing(**kwargs):
        captured.update(kwargs)
        return _row()

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_repository,
        "create_pairing",
        create_pairing,
    )

    result = service.create_outbound_pairing(
        remote_instance_id="nexus-remote",
        remote_name="Remote Nexus",
        remote_hostname="remote",
        peer_base_url="http://remote:8561",
        remote_public_key_algorithm="Ed25519",
        remote_public_key=REMOTE_KEY,
        remote_public_key_fingerprint=REMOTE_FINGERPRINT,
    )

    assert result["status"] == "ok"
    assert result["created"] is True

    assert captured["local_instance_id"] == "nexus-local"
    assert captured["remote_instance_id"] == "nexus-remote"

    # Secrets are not accepted or persisted by this foundation.
    assert "enrollment_secret" not in captured
    assert "enrollmentSecret" not in captured
    assert "secret" not in captured


def test_public_pairing_hides_transport_and_raw_key():
    payload = service._public_pairing(_row())

    assert payload["remoteInstanceId"] == "nexus-remote"
    assert payload["remotePublicKeyFingerprint"] == REMOTE_FINGERPRINT

    assert "peerBaseUrl" not in payload
    assert "remotePublicKey" not in payload
    assert "enrollmentSecret" not in payload
    assert "secret" not in payload


def test_existing_active_pairing_is_reused(monkeypatch):
    monkeypatch.setattr(
        service,
        "_local_instance_id",
        lambda: "nexus-local",
    )

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_repository,
        "get_active_pairing_for_remote",
        lambda **kwargs: _row(),
    )

    def forbidden(**kwargs):
        raise AssertionError(
            "duplicate active pairing must not be created"
        )

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_repository,
        "create_pairing",
        forbidden,
    )

    result = service.create_outbound_pairing(
        remote_instance_id="nexus-remote",
        remote_name="Remote Nexus",
        remote_hostname="remote",
        peer_base_url="http://remote:8561",
        remote_public_key_algorithm="Ed25519",
        remote_public_key=REMOTE_KEY,
        remote_public_key_fingerprint=REMOTE_FINGERPRINT,
    )

    assert result["created"] is False
    assert result["pairing"]["pairingId"] == "pairing-test"


def test_self_pairing_is_rejected(monkeypatch):
    monkeypatch.setattr(
        service,
        "_local_instance_id",
        lambda: "nexus-local",
    )

    try:
        service.create_outbound_pairing(
            remote_instance_id="nexus-local",
            remote_name="Local",
            remote_hostname="local",
            peer_base_url="http://local:8561",
            remote_public_key_algorithm="Ed25519",
            remote_public_key=REMOTE_KEY,
            remote_public_key_fingerprint=REMOTE_FINGERPRINT,
        )
    except ValueError as exc:
        assert "itself" in str(exc)
    else:
        raise AssertionError(
            "self pairing must be rejected"
        )
