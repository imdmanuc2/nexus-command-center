from datetime import datetime, timezone

import pytest

from backend.services import nexus_peer_enrollment_auth_service as service
from backend.services import nexus_peer_machine_identity_service
from backend.services import nexus_peer_request_auth_service


NOW = datetime(
    2026, 9, 1, 14, 0, 0,
    tzinfo=timezone.utc,
)

PATH = "/api/nexus/enrollment/request"


def _identity(monkeypatch):
    private_key = (
        nexus_peer_machine_identity_service
        .generate_private_key()
    )

    identity = (
        nexus_peer_machine_identity_service
        .public_identity_from_private_key(private_key)
    )

    monkeypatch.setattr(
        nexus_peer_machine_identity_service,
        "sign",
        lambda message: private_key.sign(message),
    )

    return identity


def _request(monkeypatch):
    identity = _identity(monkeypatch)

    payload = {
        "remoteInstanceId": "nexus-remote",
        "pairingId": "pairing-test",
        "capabilityHash": ("a" * 64),
        "remoteName": "Remote Nexus",
        "remoteHostname": "remote",
        "peerBaseUrl": "http://remote:8561",
        "publicKeyAlgorithm": identity["algorithm"],
        "publicKey": identity["publicKey"],
        "publicKeyFingerprint": identity["fingerprint"],
    }

    import json

    body = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    signed = nexus_peer_request_auth_service.sign_request(
        method="POST",
        path=PATH,
        sender_instance_id="nexus-remote",
        target_instance_id="nexus-local",
        timestamp=NOW,
        body=body,
    )

    headers = {
        nexus_peer_request_auth_service.HEADER_PROTOCOL:
            signed["protocol"],
        nexus_peer_request_auth_service.HEADER_ALGORITHM:
            signed["algorithm"],
        nexus_peer_request_auth_service.HEADER_SENDER:
            signed["senderInstanceId"],
        nexus_peer_request_auth_service.HEADER_TARGET:
            signed["targetInstanceId"],
        nexus_peer_request_auth_service.HEADER_TIMESTAMP:
            signed["timestamp"],
        nexus_peer_request_auth_service.HEADER_NONCE:
            signed["nonce"],
        nexus_peer_request_auth_service.HEADER_BODY_SHA256:
            signed["bodySha256"],
        nexus_peer_request_auth_service.HEADER_SIGNATURE:
            signed["signature"],
    }

    return payload, body, headers


def _local(monkeypatch):
    monkeypatch.setattr(
        service,
        "_local_instance_id",
        lambda: "nexus-local",
    )


def test_valid_unpaired_request_proves_key_possession(monkeypatch):
    _local(monkeypatch)

    payload, body, headers = _request(monkeypatch)

    claimed = []

    monkeypatch.setattr(
        service.nexus_peer_request_nonce_repository,
        "claim_nonce",
        lambda **kwargs: claimed.append(kwargs) or True,
    )

    result = service.authenticate_enrollment_request(
        method="POST",
        path=PATH,
        headers=headers,
        body=body,
        payload=payload,
        now=NOW,
    )

    assert result["authenticated"] is True
    assert result["remoteInstanceId"] == "nexus-remote"
    assert (
        result["publicKeyFingerprint"]
        == payload["publicKeyFingerprint"]
    )
    assert len(claimed) == 1


def test_body_tampering_is_rejected_before_nonce_claim(monkeypatch):
    _local(monkeypatch)

    payload, body, headers = _request(monkeypatch)

    payload = dict(payload)
    payload["remoteName"] = "Tampered"

    import json

    tampered = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    monkeypatch.setattr(
        service.nexus_peer_request_nonce_repository,
        "claim_nonce",
        lambda **kwargs: pytest.fail(
            "tampered request must not claim nonce"
        ),
    )

    with pytest.raises(
        PermissionError,
        match="body digest",
    ):
        service.authenticate_enrollment_request(
            method="POST",
            path=PATH,
            headers=headers,
            body=tampered,
            payload=payload,
            now=NOW,
        )


def test_sender_identity_mismatch_is_rejected(monkeypatch):
    _local(monkeypatch)

    payload, body, headers = _request(monkeypatch)

    payload = dict(payload)
    payload["remoteInstanceId"] = "nexus-other"

    monkeypatch.setattr(
        service.nexus_peer_request_nonce_repository,
        "claim_nonce",
        lambda **kwargs: pytest.fail(
            "identity mismatch must not claim nonce"
        ),
    )

    with pytest.raises(
        PermissionError,
        match="sender identity",
    ):
        service.authenticate_enrollment_request(
            method="POST",
            path=PATH,
            headers=headers,
            body=body,
            payload=payload,
            now=NOW,
        )


def test_public_key_fingerprint_mismatch_is_rejected(monkeypatch):
    _local(monkeypatch)

    payload, body, headers = _request(monkeypatch)

    payload = dict(payload)
    payload["publicKeyFingerprint"] = (
        "sha256:" + ("0" * 64)
    )

    monkeypatch.setattr(
        service.nexus_peer_request_nonce_repository,
        "claim_nonce",
        lambda **kwargs: pytest.fail(
            "fingerprint mismatch must not claim nonce"
        ),
    )

    with pytest.raises(
        PermissionError,
        match="fingerprint mismatch",
    ):
        service.authenticate_enrollment_request(
            method="POST",
            path=PATH,
            headers=headers,
            body=body,
            payload=payload,
            now=NOW,
        )


def test_replay_is_rejected(monkeypatch):
    _local(monkeypatch)

    payload, body, headers = _request(monkeypatch)

    monkeypatch.setattr(
        service.nexus_peer_request_nonce_repository,
        "claim_nonce",
        lambda **kwargs: False,
    )

    with pytest.raises(
        PermissionError,
        match="replay",
    ):
        service.authenticate_enrollment_request(
            method="POST",
            path=PATH,
            headers=headers,
            body=body,
            payload=payload,
            now=NOW,
        )


def test_wrong_target_is_rejected_before_nonce_claim(monkeypatch):
    _local(monkeypatch)

    payload, body, headers = _request(monkeypatch)

    headers = dict(headers)
    headers[
        nexus_peer_request_auth_service.HEADER_TARGET
    ] = "nexus-somewhere-else"

    monkeypatch.setattr(
        service.nexus_peer_request_nonce_repository,
        "claim_nonce",
        lambda **kwargs: pytest.fail(
            "wrong target must not claim nonce"
        ),
    )

    with pytest.raises(
        PermissionError,
        match="target",
    ):
        service.authenticate_enrollment_request(
            method="POST",
            path=PATH,
            headers=headers,
            body=body,
            payload=payload,
            now=NOW,
        )
