"""Tests for outbound signed Nexus peer requests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.services import (
    nexus_peer_request_auth_service as auth,
)
from backend.services import (
    nexus_peer_signed_client_service as client,
)


LOCAL = "nexus-local"
REMOTE = "nexus-remote"

TIMESTAMP = datetime(
    2026,
    8,
    29,
    21,
    0,
    0,
    tzinfo=timezone.utc,
)

NONCE = (
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
)


def _peer(**overrides):
    value = {
        "peer_id": "peer-test",
        "local_instance_id": LOCAL,
        "remote_instance_id": REMOTE,
        "peer_base_url":
            "http://192.0.2.10:8561",
        "status": "verified",
        "enabled": True,
    }

    value.update(overrides)
    return value


def _local(monkeypatch):
    monkeypatch.setattr(
        client.nexus_instance_service,
        "get_local_instance",
        lambda: {
            "instance_id": LOCAL,
        },
    )


def test_peer_status_path_is_locked():
    assert (
        client.PEER_STATUS_PATH
        == "/api/nexus/peer/status"
    )


def test_peer_status_url_uses_normalized_base():
    assert (
        client.peer_status_url(
            "http://192.0.2.10:8561/"
        )
        == (
            "http://192.0.2.10:8561"
            "/api/nexus/peer/status"
        )
    )


def test_builder_binds_local_and_remote_identity(
    monkeypatch,
):
    _local(monkeypatch)

    captured = {}

    def fake_sign_request(**kwargs):
        captured.update(kwargs)

        return {
            "protocol": auth.AUTH_PROTOCOL,
            "algorithm": auth.SIGNATURE_ALGORITHM,
            "senderInstanceId": LOCAL,
            "targetInstanceId": REMOTE,
            "timestamp": "2026-08-29T21:00:00Z",
            "nonce": NONCE,
            "bodySha256": "digest",
            "signature": "signature",
        }

    monkeypatch.setattr(
        client.nexus_peer_request_auth_service,
        "sign_request",
        fake_sign_request,
    )

    result = (
        client.build_signed_peer_status_request(
            peer=_peer(),
            timestamp=TIMESTAMP,
            nonce=NONCE,
        )
    )

    assert captured == {
        "method": "GET",
        "path": client.PEER_STATUS_PATH,
        "sender_instance_id": LOCAL,
        "target_instance_id": REMOTE,
        "timestamp": TIMESTAMP,
        "body": b"",
        "nonce": NONCE,
    }

    assert result["method"] == "GET"
    assert result["body"] == b""
    assert result["localInstanceId"] == LOCAL
    assert result["remoteInstanceId"] == REMOTE


def test_builder_emits_exact_auth_headers(
    monkeypatch,
):
    _local(monkeypatch)

    monkeypatch.setattr(
        client.nexus_peer_request_auth_service,
        "sign_request",
        lambda **kwargs: {
            "protocol": auth.AUTH_PROTOCOL,
            "algorithm": auth.SIGNATURE_ALGORITHM,
            "senderInstanceId": LOCAL,
            "targetInstanceId": REMOTE,
            "timestamp": "2026-08-29T21:00:00Z",
            "nonce": NONCE,
            "bodySha256": "digest",
            "signature": "signature",
        },
    )

    result = (
        client.build_signed_peer_status_request(
            peer=_peer(),
            timestamp=TIMESTAMP,
            nonce=NONCE,
        )
    )

    assert set(result["headers"]) == set(
        auth.AUTH_HEADERS
    )

    assert (
        result["headers"][auth.HEADER_SENDER]
        == LOCAL
    )

    assert (
        result["headers"][auth.HEADER_TARGET]
        == REMOTE
    )


def test_builder_uses_exact_status_url(
    monkeypatch,
):
    _local(monkeypatch)

    monkeypatch.setattr(
        client.nexus_peer_request_auth_service,
        "sign_request",
        lambda **kwargs: {
            "protocol": auth.AUTH_PROTOCOL,
            "algorithm": auth.SIGNATURE_ALGORITHM,
            "senderInstanceId": LOCAL,
            "targetInstanceId": REMOTE,
            "timestamp": "2026-08-29T21:00:00Z",
            "nonce": NONCE,
            "bodySha256": "digest",
            "signature": "signature",
        },
    )

    result = (
        client.build_signed_peer_status_request(
            peer=_peer(),
            timestamp=TIMESTAMP,
            nonce=NONCE,
        )
    )

    assert result["url"] == (
        "http://192.0.2.10:8561"
        "/api/nexus/peer/status"
    )

    assert result["path"] == (
        "/api/nexus/peer/status"
    )


def test_builder_rejects_missing_remote(
    monkeypatch,
):
    _local(monkeypatch)

    with pytest.raises(
        ValueError,
        match="remote_instance_id",
    ):
        client.build_signed_peer_status_request(
            peer=_peer(
                remote_instance_id=""
            ),
            timestamp=TIMESTAMP,
            nonce=NONCE,
        )


def test_builder_rejects_missing_base_url(
    monkeypatch,
):
    _local(monkeypatch)

    with pytest.raises(
        ValueError,
        match="peer_base_url",
    ):
        client.build_signed_peer_status_request(
            peer=_peer(
                peer_base_url=""
            ),
            timestamp=TIMESTAMP,
            nonce=NONCE,
        )


def test_builder_rejects_self_peer(
    monkeypatch,
):
    _local(monkeypatch)

    with pytest.raises(
        ValueError,
        match="local Nexus",
    ):
        client.build_signed_peer_status_request(
            peer=_peer(
                remote_instance_id=LOCAL
            ),
            timestamp=TIMESTAMP,
            nonce=NONCE,
        )


def test_builder_performs_no_network_io():
    import inspect

    source = inspect.getsource(
        client.build_signed_peer_status_request
    )

    assert "urlopen(" not in source
    assert "Request(" not in source
    assert "requests." not in source
    assert "httpx." not in source


def test_builder_does_not_accept_remote_public_key():
    import inspect

    signature = inspect.signature(
        client.build_signed_peer_status_request
    )

    assert "public_key" not in signature.parameters
    assert "publicKey" not in signature.parameters


def test_builder_does_not_enable_capabilities():
    source = open(
        client.__file__,
        encoding="utf-8",
    ).read()

    for field in (
        "federation_enabled",
        "cmdb_exchange_enabled",
        "discovery_exchange_enabled",
        "management_enabled",
        "authority_delegation_enabled",
    ):
        assert field not in source


def test_builder_rejects_unverified_peer(
    monkeypatch,
):
    _local(monkeypatch)

    with pytest.raises(
        PermissionError,
        match="not verified",
    ):
        client.build_signed_peer_status_request(
            peer=_peer(
                status="configured",
            ),
            timestamp=TIMESTAMP,
            nonce=NONCE,
        )


def test_builder_rejects_disabled_peer(
    monkeypatch,
):
    _local(monkeypatch)

    with pytest.raises(
        PermissionError,
        match="not enabled",
    ):
        client.build_signed_peer_status_request(
            peer=_peer(
                enabled=False,
            ),
            timestamp=TIMESTAMP,
            nonce=NONCE,
        )


def test_builder_rejects_peer_owned_by_other_local_instance(
    monkeypatch,
):
    _local(monkeypatch)

    with pytest.raises(
        PermissionError,
        match="does not belong",
    ):
        client.build_signed_peer_status_request(
            peer=_peer(
                local_instance_id="nexus-other-local",
            ),
            timestamp=TIMESTAMP,
            nonce=NONCE,
        )


def test_builder_does_not_query_peer_repository():
    source = open(
        client.__file__,
        encoding="utf-8",
    ).read()

    assert "nexus_peer_repository" not in source
    assert "get_peer_by_instances" not in source
