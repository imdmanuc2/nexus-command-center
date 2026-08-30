from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.services import nexus_peer_machine_identity_service as machine
from backend.services import nexus_peer_request_auth_service as request_auth
from backend.services import nexus_peer_verified_auth_service as verified_auth


LOCAL = "nexus-local"
REMOTE = "nexus-remote"
NOW = datetime(
    2026, 8, 29, 21, 0, 0,
    tzinfo=timezone.utc,
)


def _identity(tmp_path, monkeypatch):
    path = tmp_path / "remote-machine.key"

    monkeypatch.setenv(
        "NEXUS_PEER_MACHINE_PRIVATE_KEY_FILE",
        str(path),
    )

    machine.load_or_create_private_key()

    return machine.local_public_identity()


def _peer(identity, **overrides):
    result = {
        "peer_id": "peer-nexus-remote",
        "local_instance_id": LOCAL,
        "remote_instance_id": REMOTE,
        "status": "verified",
        "enabled": True,
        "public_key_algorithm": identity["algorithm"],
        "public_key": identity["publicKey"],
        "public_key_fingerprint": identity["fingerprint"],
        "federation_enabled": False,
        "cmdb_exchange_enabled": False,
        "discovery_exchange_enabled": False,
        "management_enabled": False,
        "authority_delegation_enabled": False,
    }

    result.update(overrides)
    return result


def _signed_headers(
    *,
    body,
    nonce=None,
    sender=REMOTE,
    target=LOCAL,
):
    signed = request_auth.sign_request(
        method="POST",
        path="/api/nexus/protected-test",
        sender_instance_id=sender,
        target_instance_id=target,
        timestamp="2026-08-29T21:00:00Z",
        nonce=nonce,
        body=body,
    )

    return {
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


def _install_dependencies(
    monkeypatch,
    *,
    peer,
    claim=True,
):
    monkeypatch.setattr(
        verified_auth.nexus_instance_service,
        "get_local_instance",
        lambda: {
            "instance_id": LOCAL,
        },
    )

    captured = {}

    def get_peer_by_instances(**kwargs):
        captured["lookup"] = kwargs
        return peer

    def claim_nonce(**kwargs):
        captured["claim"] = kwargs
        return claim

    monkeypatch.setattr(
        verified_auth.nexus_peer_repository,
        "get_peer_by_instances",
        get_peer_by_instances,
    )

    monkeypatch.setattr(
        verified_auth.nexus_peer_request_nonce_repository,
        "claim_nonce",
        claim_nonce,
    )

    return captured


def test_valid_registered_peer_authenticates(
    tmp_path,
    monkeypatch,
):
    identity = _identity(
        tmp_path,
        monkeypatch,
    )

    peer = _peer(identity)

    captured = _install_dependencies(
        monkeypatch,
        peer=peer,
    )

    body = b'{"hello":"peer"}'
    headers = _signed_headers(body=body)

    result = verified_auth.authenticate_request(
        method="POST",
        path="/api/nexus/protected-test",
        headers=headers,
        body=body,
        now=NOW,
    )

    assert result["authenticated"] is True
    assert result["remoteInstanceId"] == REMOTE
    assert (
        result["publicKeyFingerprint"]
        == identity["fingerprint"]
    )

    assert captured["lookup"] == {
        "local_instance_id": LOCAL,
        "remote_instance_id": REMOTE,
    }

    assert captured["claim"]["local_instance_id"] == LOCAL
    assert captured["claim"]["remote_instance_id"] == REMOTE


def test_header_names_are_case_insensitive(
    tmp_path,
    monkeypatch,
):
    identity = _identity(tmp_path, monkeypatch)

    _install_dependencies(
        monkeypatch,
        peer=_peer(identity),
    )

    body = b"hello"
    headers = {
        key.lower(): value
        for key, value
        in _signed_headers(body=body).items()
    }

    result = verified_auth.authenticate_request(
        method="POST",
        path="/api/nexus/protected-test",
        headers=headers,
        body=body,
        now=NOW,
    )

    assert result["authenticated"] is True


def test_unknown_peer_rejected_before_nonce_claim(
    tmp_path,
    monkeypatch,
):
    _identity(tmp_path, monkeypatch)

    captured = _install_dependencies(
        monkeypatch,
        peer=None,
    )

    body = b"hello"
    headers = _signed_headers(body=body)

    with pytest.raises(
        PermissionError,
        match="not registered",
    ):
        verified_auth.authenticate_request(
            method="POST",
            path="/api/nexus/protected-test",
            headers=headers,
            body=body,
            now=NOW,
        )

    assert "claim" not in captured


@pytest.mark.parametrize(
    ("overrides", "message"),
    (
        ({"status": "configured"}, "not verified"),
        ({"enabled": False}, "disabled"),
        (
            {"public_key": None},
            "no bound machine identity",
        ),
    ),
)
def test_untrusted_peer_states_rejected_before_nonce_claim(
    tmp_path,
    monkeypatch,
    overrides,
    message,
):
    identity = _identity(tmp_path, monkeypatch)

    captured = _install_dependencies(
        monkeypatch,
        peer=_peer(
            identity,
            **overrides,
        ),
    )

    body = b"hello"
    headers = _signed_headers(body=body)

    with pytest.raises(
        PermissionError,
        match=message,
    ):
        verified_auth.authenticate_request(
            method="POST",
            path="/api/nexus/protected-test",
            headers=headers,
            body=body,
            now=NOW,
        )

    assert "claim" not in captured


def test_target_mismatch_rejected_before_peer_lookup(
    tmp_path,
    monkeypatch,
):
    _identity(tmp_path, monkeypatch)

    monkeypatch.setattr(
        verified_auth.nexus_instance_service,
        "get_local_instance",
        lambda: {"instance_id": LOCAL},
    )

    def forbidden_lookup(**kwargs):
        raise AssertionError(
            "peer lookup must not occur"
        )

    monkeypatch.setattr(
        verified_auth.nexus_peer_repository,
        "get_peer_by_instances",
        forbidden_lookup,
    )

    body = b"hello"

    headers = _signed_headers(
        body=body,
        target="nexus-other",
    )

    with pytest.raises(
        PermissionError,
        match="target",
    ):
        verified_auth.authenticate_request(
            method="POST",
            path="/api/nexus/protected-test",
            headers=headers,
            body=body,
            now=NOW,
        )


def test_body_tampering_rejected_before_nonce_claim(
    tmp_path,
    monkeypatch,
):
    identity = _identity(tmp_path, monkeypatch)

    captured = _install_dependencies(
        monkeypatch,
        peer=_peer(identity),
    )

    headers = _signed_headers(
        body=b"original",
    )

    with pytest.raises(
        PermissionError,
        match="body digest",
    ):
        verified_auth.authenticate_request(
            method="POST",
            path="/api/nexus/protected-test",
            headers=headers,
            body=b"tampered",
            now=NOW,
        )

    assert "claim" not in captured


def test_signature_tampering_rejected_before_nonce_claim(
    tmp_path,
    monkeypatch,
):
    identity = _identity(tmp_path, monkeypatch)

    captured = _install_dependencies(
        monkeypatch,
        peer=_peer(identity),
    )

    body = b"hello"
    headers = _signed_headers(body=body)

    signature = headers[
        request_auth.HEADER_SIGNATURE
    ]

    # Tamper with an actual decoded signature byte.
    # Changing only the final base64url character can
    # alter unused encoding bits without changing the
    # decoded 64-byte Ed25519 signature.
    raw_signature = bytearray(
        request_auth._base64url_decode(
            signature,
            field="signature",
        )
    )

    assert len(raw_signature) == 64

    raw_signature[0] ^= 0x01

    headers[
        request_auth.HEADER_SIGNATURE
    ] = request_auth._base64url_encode(
        bytes(raw_signature)
    )

    with pytest.raises(
        PermissionError,
        match="signature",
    ):
        verified_auth.authenticate_request(
            method="POST",
            path="/api/nexus/protected-test",
            headers=headers,
            body=body,
            now=NOW,
        )

    assert "claim" not in captured


def test_stale_timestamp_rejected_before_nonce_claim(
    tmp_path,
    monkeypatch,
):
    identity = _identity(tmp_path, monkeypatch)

    captured = _install_dependencies(
        monkeypatch,
        peer=_peer(identity),
    )

    body = b"hello"

    signed = request_auth.sign_request(
        method="POST",
        path="/api/nexus/protected-test",
        sender_instance_id=REMOTE,
        target_instance_id=LOCAL,
        timestamp="2026-08-29T20:00:00Z",
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

    with pytest.raises(
        PermissionError,
        match="clock-skew",
    ):
        verified_auth.authenticate_request(
            method="POST",
            path="/api/nexus/protected-test",
            headers=headers,
            body=body,
            now=NOW,
        )

    assert "claim" not in captured


def test_replay_claim_is_last_security_step(
    tmp_path,
    monkeypatch,
):
    identity = _identity(tmp_path, monkeypatch)

    captured = _install_dependencies(
        monkeypatch,
        peer=_peer(identity),
        claim=False,
    )

    body = b"hello"
    headers = _signed_headers(body=body)

    with pytest.raises(
        PermissionError,
        match="replay detected",
    ):
        verified_auth.authenticate_request(
            method="POST",
            path="/api/nexus/protected-test",
            headers=headers,
            body=body,
            now=NOW,
        )

    assert "claim" in captured


def test_registered_fingerprint_mismatch_rejected(
    tmp_path,
    monkeypatch,
):
    identity = _identity(tmp_path, monkeypatch)

    captured = _install_dependencies(
        monkeypatch,
        peer=_peer(
            identity,
            public_key_fingerprint=(
                "sha256:" + ("0" * 64)
            ),
        ),
    )

    body = b"hello"
    headers = _signed_headers(body=body)

    with pytest.raises(
        PermissionError,
        match="fingerprint mismatch",
    ):
        verified_auth.authenticate_request(
            method="POST",
            path="/api/nexus/protected-test",
            headers=headers,
            body=body,
            now=NOW,
        )

    assert "claim" not in captured


def test_authenticator_never_enables_capabilities(
    tmp_path,
    monkeypatch,
):
    identity = _identity(tmp_path, monkeypatch)

    peer = _peer(identity)

    _install_dependencies(
        monkeypatch,
        peer=peer,
    )

    body = b"hello"
    headers = _signed_headers(body=body)

    verified_auth.authenticate_request(
        method="POST",
        path="/api/nexus/protected-test",
        headers=headers,
        body=body,
        now=NOW,
    )

    assert peer["federation_enabled"] is False
    assert peer["cmdb_exchange_enabled"] is False
    assert peer["discovery_exchange_enabled"] is False
    assert peer["management_enabled"] is False
    assert peer["authority_delegation_enabled"] is False


def test_duplicate_auth_header_rejected_http_message():
    from email.message import Message

    headers = Message()

    for name in request_auth.AUTH_HEADERS:
        headers[name] = "placeholder"

    headers[
        request_auth.HEADER_PROTOCOL
    ] = request_auth.AUTH_PROTOCOL

    with pytest.raises(
        PermissionError,
        match="Duplicate Nexus peer authentication header",
    ):
        verified_auth._header_map(
            headers
        )


def test_duplicate_auth_header_rejected_case_variant_mapping():
    class DuplicateMapping:
        def items(self):
            return [
                (
                    request_auth.HEADER_PROTOCOL,
                    request_auth.AUTH_PROTOCOL,
                ),
                (
                    request_auth.HEADER_PROTOCOL.lower(),
                    request_auth.AUTH_PROTOCOL,
                ),
            ]

    with pytest.raises(
        PermissionError,
        match="Duplicate Nexus peer authentication header",
    ):
        verified_auth._header_map(
            DuplicateMapping()
        )


def test_non_auth_duplicate_case_does_not_create_auth_ambiguity():
    class MappingWithOrdinaryHeaders:
        def items(self):
            return [
                ("Accept", "application/json"),
                ("accept", "application/json"),
                (
                    request_auth.HEADER_PROTOCOL,
                    request_auth.AUTH_PROTOCOL,
                ),
            ]

    result = verified_auth._header_map(
        MappingWithOrdinaryHeaders()
    )

    assert (
        result[
            request_auth.HEADER_PROTOCOL.lower()
        ]
        == request_auth.AUTH_PROTOCOL
    )


def test_malformed_stored_public_key_is_auth_denial(
    tmp_path,
    monkeypatch,
):
    identity = _identity(
        tmp_path,
        monkeypatch,
    )

    captured = _install_dependencies(
        monkeypatch,
        peer=_peer(
            identity,
            public_key="not-a-valid-ed25519-key",
        ),
    )

    body = b"hello"
    headers = _signed_headers(
        body=body,
    )

    with pytest.raises(
        PermissionError,
        match="machine identity is invalid",
    ):
        verified_auth.authenticate_request(
            method="POST",
            path="/api/nexus/protected-test",
            headers=headers,
            body=body,
            now=NOW,
        )

    assert "claim" not in captured


def test_wrong_length_stored_public_key_is_auth_denial(
    tmp_path,
    monkeypatch,
):
    identity = _identity(
        tmp_path,
        monkeypatch,
    )

    captured = _install_dependencies(
        monkeypatch,
        peer=_peer(
            identity,
            public_key="QQ",
        ),
    )

    body = b"hello"
    headers = _signed_headers(
        body=body,
    )

    with pytest.raises(
        PermissionError,
        match="machine identity is invalid",
    ):
        verified_auth.authenticate_request(
            method="POST",
            path="/api/nexus/protected-test",
            headers=headers,
            body=body,
            now=NOW,
        )

    assert "claim" not in captured
