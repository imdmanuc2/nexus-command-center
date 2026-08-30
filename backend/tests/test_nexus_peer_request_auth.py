"""Regression tests for the Nexus signed peer request contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.services import nexus_peer_machine_identity_service
from backend.services import nexus_peer_request_auth_service


def _identity(tmp_path: Path):
    path = tmp_path / "machine.key"

    key = (
        nexus_peer_machine_identity_service
        .generate_private_key()
    )

    nexus_peer_machine_identity_service.persist_private_key(
        key,
        path=path,
    )

    identity = (
        nexus_peer_machine_identity_service
        .public_identity_from_private_key(
            key
        )
    )

    return path, identity


def test_canonical_request_is_deterministic():
    digest = (
        nexus_peer_request_auth_service
        .body_sha256(b'{"hello":"world"}')
    )

    first = (
        nexus_peer_request_auth_service
        .canonical_request(
            method="post",
            path="/api/nexus/test",
            sender_instance_id="nexus-a",
            target_instance_id="nexus-b",
            timestamp="2026-08-29T09:00:00Z",
            nonce="YWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWE",
            body_sha256_value=digest,
        )
    )

    second = (
        nexus_peer_request_auth_service
        .canonical_request(
            method="POST",
            path="/api/nexus/test",
            sender_instance_id="nexus-a",
            target_instance_id="nexus-b",
            timestamp="2026-08-29T09:00:00Z",
            nonce="YWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWE",
            body_sha256_value=digest.upper(),
        )
    )

    assert first == second

    assert first.startswith(
        b"protocol:nexus-peer-auth-v1\n"
    )

    assert first.endswith(
        f"bodySha256:{digest}\n".encode()
    )


def test_sign_and_verify_round_trip(
    tmp_path,
    monkeypatch,
):
    path, identity = _identity(
        tmp_path
    )

    monkeypatch.setenv(
        "NEXUS_PEER_MACHINE_PRIVATE_KEY_FILE",
        str(path),
    )

    body = b'{"operation":"health"}'

    auth = (
        nexus_peer_request_auth_service
        .sign_request(
            method="POST",
            path="/api/nexus/test",
            sender_instance_id="nexus-a",
            target_instance_id="nexus-b",
            timestamp="2026-08-29T09:00:00Z",
            nonce="YWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWE",
            body=body,
        )
    )

    assert auth["protocol"] == (
        "nexus-peer-auth-v1"
    )

    assert auth["algorithm"] == "Ed25519"

    assert (
        nexus_peer_request_auth_service
        .verify_signature(
            public_key=identity["publicKey"],
            method="POST",
            path="/api/nexus/test",
            sender_instance_id=auth[
                "senderInstanceId"
            ],
            target_instance_id=auth[
                "targetInstanceId"
            ],
            timestamp=auth["timestamp"],
            nonce=auth["nonce"],
            body_sha256_value=auth[
                "bodySha256"
            ],
            signature=auth["signature"],
        )
    )


def test_signature_binds_method_path_and_instances(
    tmp_path,
    monkeypatch,
):
    path, identity = _identity(
        tmp_path
    )

    monkeypatch.setenv(
        "NEXUS_PEER_MACHINE_PRIVATE_KEY_FILE",
        str(path),
    )

    auth = (
        nexus_peer_request_auth_service
        .sign_request(
            method="POST",
            path="/api/nexus/test",
            sender_instance_id="nexus-a",
            target_instance_id="nexus-b",
            timestamp="2026-08-29T09:00:00Z",
            nonce="YWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWE",
            body=b"{}",
        )
    )

    common = {
        "public_key": identity["publicKey"],
        "sender_instance_id":
            auth["senderInstanceId"],
        "target_instance_id":
            auth["targetInstanceId"],
        "timestamp": auth["timestamp"],
        "nonce": auth["nonce"],
        "body_sha256_value":
            auth["bodySha256"],
        "signature": auth["signature"],
    }

    assert not (
        nexus_peer_request_auth_service
        .verify_signature(
            method="GET",
            path="/api/nexus/test",
            **common,
        )
    )

    assert not (
        nexus_peer_request_auth_service
        .verify_signature(
            method="POST",
            path="/api/nexus/other",
            **common,
        )
    )

    assert not (
        nexus_peer_request_auth_service
        .verify_signature(
            method="POST",
            path="/api/nexus/test",
            **{
                **common,
                "sender_instance_id":
                    "nexus-other",
            },
        )
    )

    assert not (
        nexus_peer_request_auth_service
        .verify_signature(
            method="POST",
            path="/api/nexus/test",
            **{
                **common,
                "target_instance_id":
                    "nexus-other",
            },
        )
    )


def test_body_hash_detects_body_tampering():
    original = (
        nexus_peer_request_auth_service
        .body_sha256(b'{"value":1}')
    )

    tampered = (
        nexus_peer_request_auth_service
        .body_sha256(b'{"value":2}')
    )

    assert original != tampered


def test_invalid_signature_encoding_rejected():
    with pytest.raises(
        ValueError,
        match="signature",
    ):
        (
            nexus_peer_request_auth_service
            .verify_signature(
                public_key="unused",
                method="GET",
                path="/api/nexus/test",
                sender_instance_id="nexus-a",
                target_instance_id="nexus-b",
                timestamp="2026-08-29T09:00:00Z",
                nonce="YWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWE",
                body_sha256_value="0" * 64,
                signature="***not-base64url***",
            )
        )


def test_naive_timestamp_rejected():
    with pytest.raises(
        ValueError,
        match="canonical UTC",
    ):
        (
            nexus_peer_request_auth_service
            .canonical_request(
                method="GET",
                path="/api/nexus/test",
                sender_instance_id="nexus-a",
                target_instance_id="nexus-b",
                timestamp="2026-08-29T09:00:00",
                nonce="YWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWE",
                body_sha256_value="0" * 64,
            )
        )


def test_generated_nonce_is_canonical_256_bit_value():
    first = (
        nexus_peer_request_auth_service
        .generate_nonce()
    )

    second = (
        nexus_peer_request_auth_service
        .generate_nonce()
    )

    assert first != second

    assert (
        nexus_peer_request_auth_service
        .normalize_nonce(first)
        == first
    )

    assert (
        nexus_peer_request_auth_service
        .normalize_nonce(second)
        == second
    )


def test_short_nonce_rejected():
    with pytest.raises(
        ValueError,
        match="exactly 32 bytes",
    ):
        (
            nexus_peer_request_auth_service
            .normalize_nonce("bm9uY2U")
        )


def test_protocol_and_algorithm_validation():
    assert (
        nexus_peer_request_auth_service
        .validate_protocol(
            "nexus-peer-auth-v1"
        )
        == "nexus-peer-auth-v1"
    )

    assert (
        nexus_peer_request_auth_service
        .validate_algorithm(
            "Ed25519"
        )
        == "Ed25519"
    )

    with pytest.raises(
        ValueError,
        match="protocol",
    ):
        (
            nexus_peer_request_auth_service
            .validate_protocol(
                "nexus-peer-auth-v2"
            )
        )

    with pytest.raises(
        ValueError,
        match="algorithm",
    ):
        (
            nexus_peer_request_auth_service
            .validate_algorithm(
                "RSA"
            )
        )


def test_timestamp_freshness_window():
    from datetime import datetime, timezone

    now = datetime(
        2026,
        8,
        29,
        9,
        0,
        0,
        tzinfo=timezone.utc,
    )

    assert (
        nexus_peer_request_auth_service
        .validate_timestamp_freshness(
            "2026-08-29T08:58:00Z",
            now=now,
        )
        == "2026-08-29T08:58:00Z"
    )

    assert (
        nexus_peer_request_auth_service
        .validate_timestamp_freshness(
            "2026-08-29T09:02:00Z",
            now=now,
        )
        == "2026-08-29T09:02:00Z"
    )

    with pytest.raises(
        PermissionError,
        match="clock-skew",
    ):
        (
            nexus_peer_request_auth_service
            .validate_timestamp_freshness(
                "2026-08-29T08:57:59Z",
                now=now,
            )
        )

    with pytest.raises(
        PermissionError,
        match="clock-skew",
    ):
        (
            nexus_peer_request_auth_service
            .validate_timestamp_freshness(
                "2026-08-29T09:02:01Z",
                now=now,
            )
        )


def test_signed_fields_bind_algorithm():
    assert (
        nexus_peer_request_auth_service
        .SIGNED_FIELDS
        == (
            "protocol",
            "algorithm",
            "method",
            "path",
            "senderInstanceId",
            "targetInstanceId",
            "timestamp",
            "nonce",
            "bodySha256",
        )
    )


def test_auth_header_contract_is_locked():
    assert (
        nexus_peer_request_auth_service
        .AUTH_HEADERS
        == (
            "X-Nexus-Peer-Protocol",
            "X-Nexus-Peer-Algorithm",
            "X-Nexus-Peer-Sender",
            "X-Nexus-Peer-Target",
            "X-Nexus-Peer-Timestamp",
            "X-Nexus-Peer-Nonce",
            "X-Nexus-Peer-Body-SHA256",
            "X-Nexus-Peer-Signature",
        )
    )


def test_algorithm_line_is_cryptographically_bound(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(
        "NEXUS_PEER_MACHINE_PRIVATE_KEY_FILE",
        str(tmp_path / "machine.key"),
    )

    (
        nexus_peer_machine_identity_service
        .load_or_create_private_key()
    )

    nonce = (
        nexus_peer_request_auth_service
        .generate_nonce()
    )

    digest = (
        nexus_peer_request_auth_service
        .body_sha256(b"hello")
    )

    message = (
        nexus_peer_request_auth_service
        .canonical_request(
            protocol="nexus-peer-auth-v1",
            algorithm="Ed25519",
            method="POST",
            path="/api/nexus/test",
            sender_instance_id="nexus-a",
            target_instance_id="nexus-b",
            timestamp="2026-08-29T09:00:00Z",
            nonce=nonce,
            body_sha256_value=digest,
        )
    )

    assert (
        b"\nalgorithm:Ed25519\n"
        in message
    )

    signature = (
        nexus_peer_machine_identity_service
        .sign(message)
    )

    public_identity = (
        nexus_peer_machine_identity_service
        .local_public_identity()
    )

    tampered = message.replace(
        b"algorithm:Ed25519",
        b"algorithm:Other",
        1,
    )

    assert not (
        nexus_peer_machine_identity_service
        .verify(
            public_key=public_identity["publicKey"],
            message=tampered,
            signature=signature,
        )
    )


def test_sign_request_generates_nonce_when_omitted(
    tmp_path,
    monkeypatch,
):
    import base64

    monkeypatch.setenv(
        "NEXUS_PEER_MACHINE_PRIVATE_KEY_FILE",
        str(tmp_path / "machine.key"),
    )

    (
        nexus_peer_machine_identity_service
        .load_or_create_private_key()
    )

    auth = (
        nexus_peer_request_auth_service
        .sign_request(
            method="POST",
            path="/api/nexus/test",
            sender_instance_id="nexus-a",
            target_instance_id="nexus-b",
            timestamp="2026-08-29T09:00:00Z",
            body=b"",
        )
    )

    padding = "=" * (
        -len(auth["nonce"]) % 4
    )

    raw = base64.urlsafe_b64decode(
        auth["nonce"] + padding
    )

    assert (
        len(raw)
        == nexus_peer_request_auth_service.NONCE_BYTES
    )


def test_query_and_fragment_rejected():
    with pytest.raises(
        ValueError,
        match="query or fragment",
    ):
        (
            nexus_peer_request_auth_service
            .normalize_path(
                "/api/nexus/test?x=1"
            )
        )

    with pytest.raises(
        ValueError,
        match="query or fragment",
    ):
        (
            nexus_peer_request_auth_service
            .normalize_path(
                "/api/nexus/test#fragment"
            )
        )


def test_invalid_http_method_rejected():
    with pytest.raises(
        ValueError,
        match="HTTP token",
    ):
        (
            nexus_peer_request_auth_service
            .normalize_method(
                "POST BAD"
            )
        )

    with pytest.raises(
        ValueError,
        match="HTTP token",
    ):
        (
            nexus_peer_request_auth_service
            .normalize_method(
                "POST\nBAD"
            )
        )


def test_timestamp_wire_format_is_strict():
    assert (
        nexus_peer_request_auth_service
        .normalize_timestamp(
            "2026-08-29T09:00:00Z"
        )
        == "2026-08-29T09:00:00Z"
    )

    with pytest.raises(
        ValueError,
        match="canonical UTC",
    ):
        (
            nexus_peer_request_auth_service
            .normalize_timestamp(
                "2026-08-29T09:00:00+00:00"
            )
        )

    with pytest.raises(
        ValueError,
        match="canonical UTC",
    ):
        (
            nexus_peer_request_auth_service
            .normalize_timestamp(
                "2026-08-29T09:00:00.123Z"
            )
        )
