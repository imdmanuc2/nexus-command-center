"""Tests for signed Nexus peer HTTP transport."""

from __future__ import annotations

import io
from urllib.error import HTTPError, URLError

import pytest

from backend.services import (
    nexus_peer_signed_client_service as client,
)


LOCAL = "nexus-local"
REMOTE = "nexus-remote"
LOCAL_FINGERPRINT = (
    "sha256:"
    + ("1" * 64)
)


def _peer():
    return {
        "peer_id": "peer-test",
        "local_instance_id": LOCAL,
        "remote_instance_id": REMOTE,
        "peer_base_url":
            "http://192.0.2.10:8561",
        "status": "verified",
        "enabled": True,
    }


def _outbound():
    return {
        "method": "GET",
        "url": (
            "http://192.0.2.10:8561"
            "/api/nexus/peer/status"
        ),
        "path": "/api/nexus/peer/status",
        "headers": {
            "X-Nexus-Peer-Protocol":
                "nexus-peer-auth-v1",
            "X-Nexus-Peer-Algorithm":
                "Ed25519",
            "X-Nexus-Peer-Sender":
                LOCAL,
            "X-Nexus-Peer-Target":
                REMOTE,
            "X-Nexus-Peer-Timestamp":
                "2026-08-29T21:00:00Z",
            "X-Nexus-Peer-Nonce":
                (
                    "AAAAAAAAAAAAAAAAAAAAAAAA"
                    "AAAAAAAAAAAAAAAAAAA"
                ),
            "X-Nexus-Peer-Body-SHA256":
                "digest",
            "X-Nexus-Peer-Signature":
                "signature",
        },
        "body": b"",
        "localInstanceId": LOCAL,
        "remoteInstanceId": REMOTE,
    }


def _success_payload():
    payload = (
        '{'
        '"status":"ok",'
        '"authenticated":true,'
        '"peer":{'
        '"peerId":"peer-local-on-remote",'
        '"remoteInstanceId":"nexus-local",'
        '"publicKeyFingerprint":"'
        + LOCAL_FINGERPRINT
        + '"'
        '},'
        '"capabilities":{'
        '"peerAwareness":true,'
        '"federation":false,'
        '"cmdbExchange":false,'
        '"discoveryExchange":false,'
        '"management":false,'
        '"authorityDelegation":false'
        '}'
        '}'
    )

    return payload.encode("utf-8")



class FakeResponse:
    def __init__(
        self,
        body,
        status=200,
    ):
        self.body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False

    def getcode(self):
        return self.status

    def read(self, size=-1):
        return self.body[:size]


def _builder(monkeypatch):
    monkeypatch.setattr(
        client,
        "build_signed_peer_status_request",
        lambda **kwargs: _outbound(),
    )


def test_transport_uses_get_and_exact_headers(
    monkeypatch,
):
    _builder(monkeypatch)
    _local_machine_identity(monkeypatch)

    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout

        return FakeResponse(
            _success_payload()
        )

    monkeypatch.setattr(
        client,
        "urlopen",
        fake_urlopen,
    )

    result = client.fetch_peer_status(
        peer=_peer(),
        timeout=7,
    )

    request = captured["request"]

    assert request.get_method() == "GET"
    assert request.full_url == (
        "http://192.0.2.10:8561"
        "/api/nexus/peer/status"
    )

    assert captured["timeout"] == 7.0
    assert request.data is None

    outbound = _outbound()

    # urllib.request.Request canonicalizes header-name
    # capitalization internally. HTTP field names are
    # case-insensitive, so compare a lowercase projection
    # of the actual request header collection.
    actual_headers = {
        name.lower(): value
        for name, value
        in request.header_items()
    }

    expected_headers = {
        name.lower(): value
        for name, value
        in outbound["headers"].items()
    }

    assert actual_headers == expected_headers

    assert result["authenticated"] is True
    assert result["remoteInstanceId"] == REMOTE


def test_transport_validates_authenticated_caller(
    monkeypatch,
):
    _builder(monkeypatch)
    _local_machine_identity(monkeypatch)

    bad = _success_payload().replace(
        b'"remoteInstanceId":"nexus-local"',
        b'"remoteInstanceId":"wrong-instance"',
    )

    monkeypatch.setattr(
        client,
        "urlopen",
        lambda request, timeout:
            FakeResponse(bad),
    )

    with pytest.raises(
        RuntimeError,
        match="wrong caller identity",
    ):
        client.fetch_peer_status(
            peer=_peer()
        )


@pytest.mark.parametrize(
    "capability",
    [
        "federation",
        "cmdbExchange",
        "discoveryExchange",
        "management",
        "authorityDelegation",
    ],
)
def test_transport_rejects_dangerous_capability(
    monkeypatch,
    capability,
):
    _builder(monkeypatch)
    _local_machine_identity(monkeypatch)

    body = _success_payload().replace(
        (
            f'"{capability}":false'
        ).encode(),
        (
            f'"{capability}":true'
        ).encode(),
    )

    monkeypatch.setattr(
        client,
        "urlopen",
        lambda request, timeout:
            FakeResponse(body),
    )

    with pytest.raises(
        RuntimeError,
        match="unexpected capability state",
    ):
        client.fetch_peer_status(
            peer=_peer()
        )


def test_transport_rejects_invalid_json(
    monkeypatch,
):
    _builder(monkeypatch)

    monkeypatch.setattr(
        client,
        "urlopen",
        lambda request, timeout:
            FakeResponse(b"not-json"),
    )

    with pytest.raises(
        RuntimeError,
        match="invalid JSON",
    ):
        client.fetch_peer_status(
            peer=_peer()
        )


def test_transport_rejects_large_response(
    monkeypatch,
):
    _builder(monkeypatch)

    body = (
        b"x"
        * (
            client.MAX_RESPONSE_BODY_BYTES
            + 1
        )
    )

    monkeypatch.setattr(
        client,
        "urlopen",
        lambda request, timeout:
            FakeResponse(body),
    )

    with pytest.raises(
        RuntimeError,
        match="too large",
    ):
        client.fetch_peer_status(
            peer=_peer()
        )


def test_transport_rejects_http_error(
    monkeypatch,
):
    _builder(monkeypatch)

    def fail(request, timeout):
        raise HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            {},
            io.BytesIO(
                b'{'
                b'"status":"error",'
                b'"error":"unauthorized"'
                b'}'
            ),
        )

    monkeypatch.setattr(
        client,
        "urlopen",
        fail,
    )

    with pytest.raises(
        RuntimeError,
        match="HTTP 401",
    ):
        client.fetch_peer_status(
            peer=_peer()
        )


def test_transport_rejects_network_failure(
    monkeypatch,
):
    _builder(monkeypatch)

    def fail(request, timeout):
        raise URLError(
            "connection refused"
        )

    monkeypatch.setattr(
        client,
        "urlopen",
        fail,
    )

    with pytest.raises(
        RuntimeError,
        match="transport failed",
    ):
        client.fetch_peer_status(
            peer=_peer()
        )


@pytest.mark.parametrize(
    "timeout",
    [
        0,
        -1,
        61,
        True,
        "invalid",
    ],
)
def test_transport_rejects_invalid_timeout(
    monkeypatch,
    timeout,
):
    _builder(monkeypatch)

    with pytest.raises(
        ValueError,
        match="timeout",
    ):
        client.fetch_peer_status(
            peer=_peer(),
            timeout=timeout,
        )


def test_transport_does_not_mutate_peer(
    monkeypatch,
):
    _builder(monkeypatch)
    _local_machine_identity(monkeypatch)

    monkeypatch.setattr(
        client,
        "urlopen",
        lambda request, timeout:
            FakeResponse(
                _success_payload()
            ),
    )

    peer = _peer()
    before = dict(peer)

    client.fetch_peer_status(
        peer=peer
    )

    assert peer == before


def test_transport_has_no_repository_write_dependency():
    source = open(
        client.__file__,
        encoding="utf-8",
    ).read()

    assert "upsert_verified_peer" not in source
    assert "delete_peer" not in source
    assert "set_local_peer_connections_enabled" not in source


def _local_machine_identity(monkeypatch):
    monkeypatch.setattr(
        client.nexus_peer_machine_identity_service,
        "local_public_identity",
        lambda: {
            "algorithm": "Ed25519",
            "publicKey":
                "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "fingerprint": LOCAL_FINGERPRINT,
        },
    )


def test_transport_validates_local_machine_fingerprint(
    monkeypatch,
):
    _builder(monkeypatch)
    _local_machine_identity(monkeypatch)

    monkeypatch.setattr(
        client,
        "urlopen",
        lambda request, timeout:
            FakeResponse(
                _success_payload()
            ),
    )

    result = client.fetch_peer_status(
        peer=_peer()
    )

    assert (
        result["publicKeyFingerprint"]
        == LOCAL_FINGERPRINT
    )


def test_transport_rejects_wrong_local_machine_fingerprint(
    monkeypatch,
):
    _builder(monkeypatch)
    _local_machine_identity(monkeypatch)

    bad = _success_payload().replace(
        LOCAL_FINGERPRINT.encode(),
        (
            "sha256:"
            + ("2" * 64)
        ).encode(),
    )

    monkeypatch.setattr(
        client,
        "urlopen",
        lambda request, timeout:
            FakeResponse(bad),
    )

    with pytest.raises(
        RuntimeError,
        match="wrong machine identity",
    ):
        client.fetch_peer_status(
            peer=_peer()
        )


def test_transport_rejects_missing_local_machine_fingerprint(
    monkeypatch,
):
    _builder(monkeypatch)
    _local_machine_identity(monkeypatch)

    bad = _success_payload().replace(
        (
            '"publicKeyFingerprint":"'
            + LOCAL_FINGERPRINT
            + '"'
        ).encode(),
        b'"publicKeyFingerprint":""',
    )

    monkeypatch.setattr(
        client,
        "urlopen",
        lambda request, timeout:
            FakeResponse(bad),
    )

    with pytest.raises(
        RuntimeError,
        match="wrong machine identity",
    ):
        client.fetch_peer_status(
            peer=_peer()
        )


def test_transport_http_error_does_not_propagate_remote_detail(
    monkeypatch,
):
    _builder(monkeypatch)

    secret_detail = (
        "Nexus peer machine identity fingerprint mismatch"
    )

    def fail(request, timeout):
        raise HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            {},
            io.BytesIO(
                (
                    '{"status":"error",'
                    '"error":"unauthorized",'
                    '"message":"'
                    + secret_detail
                    + '"}'
                ).encode()
            ),
        )

    monkeypatch.setattr(
        client,
        "urlopen",
        fail,
    )

    with pytest.raises(
        RuntimeError,
    ) as captured:
        client.fetch_peer_status(
            peer=_peer()
        )

    message = str(
        captured.value
    )

    assert message == (
        "Nexus peer returned HTTP 401"
    )

    assert secret_detail not in message
    assert "fingerprint" not in message.lower()
