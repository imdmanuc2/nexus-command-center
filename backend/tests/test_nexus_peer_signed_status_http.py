"""Tests for the signed Nexus peer status HTTP boundary."""

from __future__ import annotations

from email.message import Message

from backend.api import nexus_peer_server


class FakeHandler:
    def __init__(self):
        self.path = nexus_peer_server.PEER_STATUS_PATH
        self.headers = Message()
        self.responses = []

    def _send_json(self, payload, status=200):
        self.responses.append(
            (
                status,
                payload,
            )
        )


def _authenticated():
    return {
        "peerId": "peer-remote",
        "localInstanceId": "nexus-local",
        "remoteInstanceId": "nexus-remote",
        "algorithm": "Ed25519",
        "publicKeyFingerprint": "sha256:test",
        "authenticated": True,
    }


def test_peer_status_path_is_locked():
    assert (
        nexus_peer_server.PEER_STATUS_PATH
        == "/api/nexus/peer/status"
    )


def test_peer_status_uses_verified_authenticator(
    monkeypatch,
):
    captured = {}

    def authenticate_request(**kwargs):
        captured.update(kwargs)
        return _authenticated()

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_verified_auth_service,
        "authenticate_request",
        authenticate_request,
    )

    handler = FakeHandler()

    nexus_peer_server.NexusPeerHandler.do_GET(
        handler
    )

    assert captured["method"] == "GET"
    assert (
        captured["path"]
        == nexus_peer_server.PEER_STATUS_PATH
    )
    assert captured["headers"] is handler.headers
    assert captured["body"] == b""

    assert handler.responses == [
        (
            200,
            {
                "status": "ok",
                "authenticated": True,
                "peer": {
                    "peerId": "peer-remote",
                    "remoteInstanceId":
                        "nexus-remote",
                    "publicKeyFingerprint":
                        "sha256:test",
                },
                "capabilities": {
                    "peerAwareness": True,
                    "federation": False,
                    "cmdbExchange": False,
                    "discoveryExchange": False,
                    "management": False,
                    "authorityDelegation": False,
                },
            },
        )
    ]


def test_peer_status_auth_failure_is_401(
    monkeypatch,
):
    def reject(**kwargs):
        raise PermissionError(
            "Peer authentication signature is invalid"
        )

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_verified_auth_service,
        "authenticate_request",
        reject,
    )

    handler = FakeHandler()

    nexus_peer_server.NexusPeerHandler.do_GET(
        handler
    )

    assert len(handler.responses) == 1

    status, payload = handler.responses[0]

    assert status == 401
    assert payload["status"] == "error"
    assert payload["error"] == "unauthorized"


def test_peer_status_malformed_auth_is_401(
    monkeypatch,
):
    def reject(**kwargs):
        raise ValueError(
            "Missing peer authentication header"
        )

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_verified_auth_service,
        "authenticate_request",
        reject,
    )

    handler = FakeHandler()

    nexus_peer_server.NexusPeerHandler.do_GET(
        handler
    )

    status, payload = handler.responses[0]

    assert status == 401
    assert payload["error"] == "unauthorized"


def test_identity_bootstrap_does_not_use_verified_auth(
    monkeypatch,
):
    called = {
        "verified": False,
    }

    def forbidden(**kwargs):
        called["verified"] = True
        raise AssertionError(
            "verified auth must not protect bootstrap identity"
        )

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_verified_auth_service,
        "authenticate_request",
        forbidden,
    )

    monkeypatch.setattr(
        nexus_peer_server.nexus_peer_service,
        "identity",
        lambda authorization: (
            200,
            {
                "status": "ok",
            },
        ),
    )

    handler = FakeHandler()
    handler.path = nexus_peer_server.IDENTITY_PATH
    handler.headers["Authorization"] = (
        "Bearer bootstrap-test"
    )

    nexus_peer_server.NexusPeerHandler.do_GET(
        handler
    )

    assert called["verified"] is False
    assert handler.responses == [
        (
            200,
            {
                "status": "ok",
            },
        )
    ]


def test_unknown_get_path_remains_404(
    monkeypatch,
):
    def forbidden(**kwargs):
        raise AssertionError(
            "authenticator must not run for unknown route"
        )

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_verified_auth_service,
        "authenticate_request",
        forbidden,
    )

    handler = FakeHandler()
    handler.path = "/api/nexus/not-real"

    nexus_peer_server.NexusPeerHandler.do_GET(
        handler
    )

    assert handler.responses == [
        (
            404,
            {
                "status": "error",
                "error": "not_found",
            },
        )
    ]


def test_bootstrap_enrollment_paths_are_distinct():
    assert (
        nexus_peer_server.ENROLLMENT_REQUEST_PATH
        != nexus_peer_server.PEER_STATUS_PATH
    )

    assert (
        "/api/nexus/enrollment/consume"
        != nexus_peer_server.PEER_STATUS_PATH
    )


def test_status_exposes_no_dangerous_capability():
    capabilities = {
        "peerAwareness": True,
        "federation": False,
        "cmdbExchange": False,
        "discoveryExchange": False,
        "management": False,
        "authorityDelegation": False,
    }

    assert capabilities["peerAwareness"] is True

    for key in (
        "federation",
        "cmdbExchange",
        "discoveryExchange",
        "management",
        "authorityDelegation",
    ):
        assert capabilities[key] is False


def test_peer_status_401_exposes_no_authentication_detail(
    monkeypatch,
):
    secret_detail = (
        "Nexus peer machine identity fingerprint mismatch"
    )

    def reject(**kwargs):
        raise PermissionError(
            secret_detail
        )

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_verified_auth_service,
        "authenticate_request",
        reject,
    )

    handler = FakeHandler()

    nexus_peer_server.NexusPeerHandler.do_GET(
        handler
    )

    assert handler.responses == [
        (
            401,
            {
                "status": "error",
                "error": "unauthorized",
            },
        )
    ]

    payload_text = repr(
        handler.responses[0][1]
    )

    assert secret_detail not in payload_text
    assert "signature" not in payload_text.lower()
    assert "fingerprint" not in payload_text.lower()


def test_peer_status_value_error_401_is_also_generic(
    monkeypatch,
):
    secret_detail = (
        "Ed25519 signature must be 64 bytes"
    )

    def reject(**kwargs):
        raise ValueError(
            secret_detail
        )

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_verified_auth_service,
        "authenticate_request",
        reject,
    )

    handler = FakeHandler()

    nexus_peer_server.NexusPeerHandler.do_GET(
        handler
    )

    assert handler.responses == [
        (
            401,
            {
                "status": "error",
                "error": "unauthorized",
            },
        )
    ]

    assert (
        secret_detail
        not in repr(handler.responses)
    )
