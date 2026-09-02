"""Security tests for signed Nexus enrollment status authentication."""

from datetime import datetime, timezone

import pytest

from backend.services import nexus_peer_enrollment_auth_service as service
from backend.services import nexus_peer_request_auth_service as request_auth


LOCAL = "nexus-local"
REMOTE = "nexus-remote"
ENROLLMENT = "enroll-status"
PAIRING = "pairing-status"
PATH = "/api/nexus/enrollment/status"
NOW = datetime(2026, 9, 2, 16, 0, tzinfo=timezone.utc)


def _identity(monkeypatch):
    machine = request_auth.nexus_peer_machine_identity_service
    public = machine.local_public_identity()

    monkeypatch.setattr(
        service,
        "_local_instance_id",
        lambda: LOCAL,
    )

    return public


def _signed(monkeypatch, *, payload=None):
    public = _identity(monkeypatch)

    body = (
        b'{"enrollmentId":"enroll-status",'
        b'"pairingId":"pairing-status"}'
    )

    if payload is None:
        payload = {
            "enrollmentId": ENROLLMENT,
            "pairingId": PAIRING,
        }

    signed = request_auth.sign_request(
        method="POST",
        path=PATH,
        sender_instance_id=REMOTE,
        target_instance_id=LOCAL,
        timestamp=NOW,
        body=body,
    )

    headers = {
        request_auth.HEADER_PROTOCOL:
            signed["protocol"],
        request_auth.HEADER_ALGORITHM:
            signed["algorithm"],
        request_auth.HEADER_SENDER:
            signed["senderInstanceId"],
        request_auth.HEADER_TARGET:
            signed["targetInstanceId"],
        request_auth.HEADER_TIMESTAMP:
            signed["timestamp"],
        request_auth.HEADER_NONCE:
            signed["nonce"],
        request_auth.HEADER_BODY_SHA256:
            signed["bodySha256"],
        request_auth.HEADER_SIGNATURE:
            signed["signature"],
    }

    row = {
        "local_instance_id": LOCAL,
        "requested_remote_instance_id": REMOTE,
        "request_id": PAIRING,
        "requested_public_key_algorithm":
            public["algorithm"],
        "requested_public_key":
            public["publicKey"],
        "requested_public_key_fingerprint":
            public["fingerprint"],
    }

    return body, payload, headers, row


def test_status_auth_uses_stored_identity_and_claims_nonce(monkeypatch):
    body, payload, headers, row = _signed(monkeypatch)

    monkeypatch.setattr(
        service.nexus_peer_enrollment_repository,
        "get_enrollment",
        lambda enrollment_id: (
            row if enrollment_id == ENROLLMENT else None
        ),
    )

    claims = []

    monkeypatch.setattr(
        service.nexus_peer_request_nonce_repository,
        "claim_nonce",
        lambda **kwargs: claims.append(kwargs) or True,
    )

    result = service.authenticate_enrollment_status(
        method="POST",
        path=PATH,
        headers=headers,
        body=body,
        payload=payload,
        now=NOW,
    )

    assert result["authenticated"] is True
    assert result["localInstanceId"] == LOCAL
    assert result["remoteInstanceId"] == REMOTE
    assert result["enrollmentId"] == ENROLLMENT
    assert result["pairingId"] == PAIRING
    assert len(claims) == 1


def test_status_auth_rejects_wrong_pairing_before_nonce(monkeypatch):
    body, payload, headers, row = _signed(monkeypatch)

    row["request_id"] = "different-pairing"

    monkeypatch.setattr(
        service.nexus_peer_enrollment_repository,
        "get_enrollment",
        lambda enrollment_id: row,
    )

    monkeypatch.setattr(
        service.nexus_peer_request_nonce_repository,
        "claim_nonce",
        lambda **kwargs: pytest.fail(
            "wrong pairing must not claim nonce"
        ),
    )

    with pytest.raises(
        PermissionError,
        match="pairing identity mismatch",
    ):
        service.authenticate_enrollment_status(
            method="POST",
            path=PATH,
            headers=headers,
            body=body,
            payload=payload,
            now=NOW,
        )


def test_status_auth_rejects_wrong_sender_before_nonce(monkeypatch):
    body, payload, headers, row = _signed(monkeypatch)

    row["requested_remote_instance_id"] = "other-nexus"

    monkeypatch.setattr(
        service.nexus_peer_enrollment_repository,
        "get_enrollment",
        lambda enrollment_id: row,
    )

    monkeypatch.setattr(
        service.nexus_peer_request_nonce_repository,
        "claim_nonce",
        lambda **kwargs: pytest.fail(
            "wrong sender must not claim nonce"
        ),
    )

    with pytest.raises(
        PermissionError,
        match="sender identity mismatch",
    ):
        service.authenticate_enrollment_status(
            method="POST",
            path=PATH,
            headers=headers,
            body=body,
            payload=payload,
            now=NOW,
        )


def test_status_auth_rejects_identity_or_capability_body_fields(monkeypatch):
    body, _, headers, row = _signed(monkeypatch)

    monkeypatch.setattr(
        service.nexus_peer_enrollment_repository,
        "get_enrollment",
        lambda enrollment_id: row,
    )

    for field, value in (
        ("publicKey", "forbidden"),
        ("remoteInstanceId", REMOTE),
        ("enrollmentCapability", "forbidden"),
        ("capabilityHash", "a" * 64),
    ):
        payload = {
            "enrollmentId": ENROLLMENT,
            "pairingId": PAIRING,
            field: value,
        }

        with pytest.raises(
            PermissionError,
            match="must not supply identity or capability",
        ):
            service.authenticate_enrollment_status(
                method="POST",
                path=PATH,
                headers=headers,
                body=body,
                payload=payload,
                now=NOW,
            )


def test_status_auth_replay_is_rejected(monkeypatch):
    body, payload, headers, row = _signed(monkeypatch)

    monkeypatch.setattr(
        service.nexus_peer_enrollment_repository,
        "get_enrollment",
        lambda enrollment_id: row,
    )

    monkeypatch.setattr(
        service.nexus_peer_request_nonce_repository,
        "claim_nonce",
        lambda **kwargs: False,
    )

    with pytest.raises(
        PermissionError,
        match="replay",
    ):
        service.authenticate_enrollment_status(
            method="POST",
            path=PATH,
            headers=headers,
            body=body,
            payload=payload,
            now=NOW,
        )
