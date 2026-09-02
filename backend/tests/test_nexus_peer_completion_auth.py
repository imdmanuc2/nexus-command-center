from datetime import datetime, timedelta, timezone
import json

import pytest

from backend.services import nexus_peer_enrollment_auth_service as service
from backend.services import nexus_peer_machine_identity_service
from backend.services import nexus_peer_request_auth_service


NOW = datetime(
    2026, 9, 1, 20, 0, 0,
    tzinfo=timezone.utc,
)

PATH = "/api/nexus/enrollment/complete"


def _identity(monkeypatch):
    private_key = (
        nexus_peer_machine_identity_service
        .generate_private_key()
    )

    identity = (
        nexus_peer_machine_identity_service
        .public_identity_from_private_key(
            private_key
        )
    )

    monkeypatch.setattr(
        nexus_peer_machine_identity_service,
        "sign",
        lambda message: private_key.sign(
            message
        ),
    )

    return identity


def _fixture(monkeypatch):
    identity = _identity(monkeypatch)

    enrollment = {
        "enrollment_id": "enroll-test",
        "local_instance_id": "nexus-local",
        "request_id": "pairing-test",
        "status": "approved",
        "expires_at": NOW + timedelta(
            minutes=5
        ),
        "requested_remote_instance_id":
            "nexus-remote",
        "requested_remote_name":
            "Remote Nexus",
        "requested_remote_hostname":
            "remote",
        "requested_peer_base_url":
            "http://remote:8561",
        "requested_public_key_algorithm":
            identity["algorithm"],
        "requested_public_key":
            identity["publicKey"],
        "requested_public_key_fingerprint":
            identity["fingerprint"],
    }

    payload = {
        "enrollmentId": "enroll-test",
        "pairingId": "pairing-test",
        "enrollmentCapability":
            "synthetic-completion-capability",
    }

    body = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    signed = (
        nexus_peer_request_auth_service
        .sign_request(
            method="POST",
            path=PATH,
            sender_instance_id="nexus-remote",
            target_instance_id="nexus-local",
            timestamp=NOW,
            body=body,
        )
    )

    headers = {
        nexus_peer_request_auth_service
        .HEADER_PROTOCOL:
            signed["protocol"],

        nexus_peer_request_auth_service
        .HEADER_ALGORITHM:
            signed["algorithm"],

        nexus_peer_request_auth_service
        .HEADER_SENDER:
            signed["senderInstanceId"],

        nexus_peer_request_auth_service
        .HEADER_TARGET:
            signed["targetInstanceId"],

        nexus_peer_request_auth_service
        .HEADER_TIMESTAMP:
            signed["timestamp"],

        nexus_peer_request_auth_service
        .HEADER_NONCE:
            signed["nonce"],

        nexus_peer_request_auth_service
        .HEADER_BODY_SHA256:
            signed["bodySha256"],

        nexus_peer_request_auth_service
        .HEADER_SIGNATURE:
            signed["signature"],
    }

    monkeypatch.setattr(
        service,
        "_local_instance_id",
        lambda: "nexus-local",
    )

    monkeypatch.setattr(
        service.nexus_peer_enrollment_repository,
        "get_enrollment",
        lambda enrollment_id:
            enrollment
            if enrollment_id == "enroll-test"
            else None,
    )

    return (
        identity,
        enrollment,
        payload,
        body,
        headers,
    )


def test_completion_uses_stored_identity(
    monkeypatch,
):
    (
        identity,
        enrollment,
        payload,
        body,
        headers,
    ) = _fixture(monkeypatch)

    claimed = []

    monkeypatch.setattr(
        service.nexus_peer_request_nonce_repository,
        "claim_nonce",
        lambda **kwargs:
            claimed.append(kwargs) or True,
    )

    result = (
        service
        .authenticate_enrollment_completion(
            method="POST",
            path=PATH,
            headers=headers,
            body=body,
            payload=payload,
            now=NOW,
        )
    )

    assert result["authenticated"] is True
    assert (
        result["remoteInstanceId"]
        == enrollment[
            "requested_remote_instance_id"
        ]
    )
    assert (
        result["publicKeyFingerprint"]
        == identity["fingerprint"]
    )
    assert len(claimed) == 1


def test_completion_rejects_identity_in_body(
    monkeypatch,
):
    (
        _,
        _,
        payload,
        _,
        _,
    ) = _fixture(monkeypatch)

    payload = dict(payload)
    payload["publicKey"] = "attacker-key"

    body = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    signed = (
        nexus_peer_request_auth_service
        .sign_request(
            method="POST",
            path=PATH,
            sender_instance_id="nexus-remote",
            target_instance_id="nexus-local",
            timestamp=NOW,
            body=body,
        )
    )

    headers = {
        nexus_peer_request_auth_service
        .HEADER_PROTOCOL:
            signed["protocol"],

        nexus_peer_request_auth_service
        .HEADER_ALGORITHM:
            signed["algorithm"],

        nexus_peer_request_auth_service
        .HEADER_SENDER:
            signed["senderInstanceId"],

        nexus_peer_request_auth_service
        .HEADER_TARGET:
            signed["targetInstanceId"],

        nexus_peer_request_auth_service
        .HEADER_TIMESTAMP:
            signed["timestamp"],

        nexus_peer_request_auth_service
        .HEADER_NONCE:
            signed["nonce"],

        nexus_peer_request_auth_service
        .HEADER_BODY_SHA256:
            signed["bodySha256"],

        nexus_peer_request_auth_service
        .HEADER_SIGNATURE:
            signed["signature"],
    }

    monkeypatch.setattr(
        service.nexus_peer_request_nonce_repository,
        "claim_nonce",
        lambda **kwargs: pytest.fail(
            "identity injection must fail "
            "before nonce claim"
        ),
    )

    with pytest.raises(
        PermissionError,
        match="must not supply machine identity",
    ):
        service.authenticate_enrollment_completion(
            method="POST",
            path=PATH,
            headers=headers,
            body=body,
            payload=payload,
            now=NOW,
        )


def test_wrong_signed_sender_is_rejected(
    monkeypatch,
):
    (
        _,
        _,
        payload,
        body,
        headers,
    ) = _fixture(monkeypatch)

    headers = dict(headers)
    headers[
        nexus_peer_request_auth_service
        .HEADER_SENDER
    ] = "nexus-attacker"

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
        service.authenticate_enrollment_completion(
            method="POST",
            path=PATH,
            headers=headers,
            body=body,
            payload=payload,
            now=NOW,
        )


def test_wrong_pairing_id_is_rejected(
    monkeypatch,
):
    (
        _,
        _,
        payload,
        _,
        headers,
    ) = _fixture(monkeypatch)

    payload = dict(payload)
    payload["pairingId"] = "pairing-other"

    body = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    headers = dict(headers)
    headers[
        nexus_peer_request_auth_service
        .HEADER_BODY_SHA256
    ] = (
        nexus_peer_request_auth_service
        .body_sha256(body)
    )

    monkeypatch.setattr(
        service.nexus_peer_request_nonce_repository,
        "claim_nonce",
        lambda **kwargs: pytest.fail(
            "wrong pairing id must not claim nonce"
        ),
    )

    with pytest.raises(
        PermissionError,
        match="pairing identity mismatch",
    ):
        service.authenticate_enrollment_completion(
            method="POST",
            path=PATH,
            headers=headers,
            body=body,
            payload=payload,
            now=NOW,
        )


def test_tampered_body_is_rejected(
    monkeypatch,
):
    (
        _,
        _,
        payload,
        _,
        headers,
    ) = _fixture(monkeypatch)

    tampered = dict(payload)
    tampered["enrollmentCapability"] = (
        "tampered-capability"
    )

    tampered_body = json.dumps(
        tampered,
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
        service.authenticate_enrollment_completion(
            method="POST",
            path=PATH,
            headers=headers,
            body=tampered_body,
            payload=tampered,
            now=NOW,
        )


def test_stored_fingerprint_mismatch_rejected(
    monkeypatch,
):
    (
        _,
        enrollment,
        payload,
        body,
        headers,
    ) = _fixture(monkeypatch)

    enrollment[
        "requested_public_key_fingerprint"
    ] = "sha256:" + ("0" * 64)

    monkeypatch.setattr(
        service.nexus_peer_request_nonce_repository,
        "claim_nonce",
        lambda **kwargs: pytest.fail(
            "bad stored identity must not claim nonce"
        ),
    )

    with pytest.raises(
        PermissionError,
        match="stored fingerprint mismatch",
    ):
        service.authenticate_enrollment_completion(
            method="POST",
            path=PATH,
            headers=headers,
            body=body,
            payload=payload,
            now=NOW,
        )


def test_completion_replay_rejected(
    monkeypatch,
):
    (
        _,
        _,
        payload,
        body,
        headers,
    ) = _fixture(monkeypatch)

    monkeypatch.setattr(
        service.nexus_peer_request_nonce_repository,
        "claim_nonce",
        lambda **kwargs: False,
    )

    with pytest.raises(
        PermissionError,
        match="replay",
    ):
        service.authenticate_enrollment_completion(
            method="POST",
            path=PATH,
            headers=headers,
            body=body,
            payload=payload,
            now=NOW,
        )


def test_wrong_target_rejected(
    monkeypatch,
):
    (
        _,
        _,
        payload,
        body,
        headers,
    ) = _fixture(monkeypatch)

    headers = dict(headers)
    headers[
        nexus_peer_request_auth_service
        .HEADER_TARGET
    ] = "nexus-other"

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
        service.authenticate_enrollment_completion(
            method="POST",
            path=PATH,
            headers=headers,
            body=body,
            payload=payload,
            now=NOW,
        )
