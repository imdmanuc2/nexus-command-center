"""HTTP contract tests for signed Nexus enrollment status."""

import io
import json

from backend.api import nexus_peer_server


PATH = "/api/nexus/enrollment/status"


class FakeHeaders(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class Handler:
    def __init__(
        self,
        *,
        payload,
        headers=None,
    ):
        self.path = PATH
        self.command = "POST"

        self.raw_body = json.dumps(
            payload,
            separators=(",", ":"),
        ).encode("utf-8")

        self.rfile = io.BytesIO(
            self.raw_body
        )

        self.headers = FakeHeaders(
            headers or {}
        )

        self.headers.setdefault(
            "Content-Length",
            str(len(self.raw_body)),
        )

        self.response_status = None
        self.response_payload = None

    def _send_json(
        self,
        payload,
        status=200,
    ):
        self.response_status = status
        self.response_payload = payload

    def _read_json_body(self):
        return (
            json.loads(
                self.raw_body.decode("utf-8")
            ),
            self.raw_body,
        )


def _run(handler):
    nexus_peer_server.NexusPeerHandler.do_POST(
        handler
    )


def test_status_path_is_locked():
    assert (
        nexus_peer_server.ENROLLMENT_STATUS_PATH
        == "/api/nexus/enrollment/status"
    )


def test_status_authentication_occurs_before_lookup(monkeypatch):
    events = []

    def authenticate(**kwargs):
        events.append("authenticate")

        assert kwargs["method"] == "POST"
        assert kwargs["path"] == PATH

        return {
            "authenticated": True,
            "remoteInstanceId":
                "nexus-remote",
            "enrollmentId":
                "enroll-status",
            "pairingId":
                "pairing-status",
        }

    def lookup(**kwargs):
        events.append("lookup")

        assert kwargs == {
            "enrollment_id":
                "enroll-status",
            "pairing_id":
                "pairing-status",
            "authenticated_remote_instance_id":
                "nexus-remote",
        }

        return {
            "status": "ok",
            "enrollmentId":
                "enroll-status",
            "pairingId":
                "pairing-status",
            "localInstanceId":
                "nexus-local",
            "remoteInstanceId":
                "nexus-remote",
            "enrollmentStatus":
                "approved",
            "expiresAt":
                "2026-09-02T18:00:00+00:00",
        }

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_auth_service,
        "authenticate_enrollment_status",
        authenticate,
    )

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_service,
        "get_remote_enrollment_status",
        lookup,
    )

    handler = Handler(
        payload={
            "enrollmentId":
                "enroll-status",
            "pairingId":
                "pairing-status",
        }
    )

    _run(handler)

    assert events == [
        "authenticate",
        "lookup",
    ]
    assert handler.response_status == 200
    assert (
        handler.response_payload[
            "enrollmentStatus"
        ]
        == "approved"
    )


def test_authenticator_receives_exact_raw_body(monkeypatch):
    captured = {}

    def authenticate(**kwargs):
        captured.update(kwargs)

        return {
            "authenticated": True,
            "remoteInstanceId":
                "nexus-remote",
            "enrollmentId":
                "enroll-status",
            "pairingId":
                "pairing-status",
        }

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_auth_service,
        "authenticate_enrollment_status",
        authenticate,
    )

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_service,
        "get_remote_enrollment_status",
        lambda **kwargs: {
            "status": "ok",
            "enrollmentId":
                "enroll-status",
            "pairingId":
                "pairing-status",
            "localInstanceId":
                "nexus-local",
            "remoteInstanceId":
                "nexus-remote",
            "enrollmentStatus":
                "pending",
            "expiresAt": None,
        },
    )

    handler = Handler(
        payload={
            "enrollmentId":
                "enroll-status",
            "pairingId":
                "pairing-status",
        }
    )

    _run(handler)

    assert captured["body"] is handler.raw_body
    assert captured["headers"] is handler.headers


def test_auth_failure_never_calls_status_service(monkeypatch):
    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_auth_service,
        "authenticate_enrollment_status",
        lambda **kwargs: (
            _raise_permission()
        ),
    )

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_service,
        "get_remote_enrollment_status",
        lambda **kwargs: (
            _unexpected_service_call()
        ),
    )

    handler = Handler(
        payload={
            "enrollmentId":
                "enroll-status",
            "pairingId":
                "pairing-status",
        }
    )

    _run(handler)

    assert handler.response_status == 403
    assert handler.response_payload == {
        "status": "error",
        "error":
            "enrollment_status_authentication_failed",
    }


def _raise_permission():
    raise PermissionError(
        "synthetic secret authentication detail"
    )


def _unexpected_service_call():
    raise AssertionError(
        "unauthenticated status request reached service"
    )


def test_service_failure_is_fixed_and_secret_free(monkeypatch):
    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_auth_service,
        "authenticate_enrollment_status",
        lambda **kwargs: {
            "authenticated": True,
            "remoteInstanceId":
                "nexus-remote",
            "enrollmentId":
                "enroll-status",
            "pairingId":
                "pairing-status",
        },
    )

    def fail(**kwargs):
        raise PermissionError(
            "sensitive enrollment lookup detail"
        )

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_service,
        "get_remote_enrollment_status",
        fail,
    )

    handler = Handler(
        payload={
            "enrollmentId":
                "enroll-status",
            "pairingId":
                "pairing-status",
        }
    )

    _run(handler)

    assert handler.response_status == 403
    assert handler.response_payload == {
        "status": "error",
        "error":
            "enrollment_status_failed",
    }

    response = repr(
        handler.response_payload
    ).lower()

    assert "sensitive" not in response
    assert "signature" not in response
    assert "publickey" not in response
    assert "capability" not in response


def test_unexpected_field_never_authenticates(monkeypatch):
    called = []

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_auth_service,
        "authenticate_enrollment_status",
        lambda **kwargs: (
            called.append(True)
        ),
    )

    handler = Handler(
        payload={
            "enrollmentId":
                "enroll-status",
            "pairingId":
                "pairing-status",
            "publicKey":
                "must-not-be-accepted",
        }
    )

    _run(handler)

    assert called == []
    assert handler.response_status in {
        400,
        422,
    }


def test_success_response_contains_no_protocol_secrets(monkeypatch):
    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_auth_service,
        "authenticate_enrollment_status",
        lambda **kwargs: {
            "authenticated": True,
            "remoteInstanceId":
                "nexus-remote",
            "enrollmentId":
                "enroll-status",
            "pairingId":
                "pairing-status",
        },
    )

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_service,
        "get_remote_enrollment_status",
        lambda **kwargs: {
            "status": "ok",
            "enrollmentId":
                "enroll-status",
            "pairingId":
                "pairing-status",
            "localInstanceId":
                "nexus-local",
            "remoteInstanceId":
                "nexus-remote",
            "enrollmentStatus":
                "approved",
            "expiresAt":
                "2026-09-02T18:00:00+00:00",
        },
    )

    handler = Handler(
        payload={
            "enrollmentId":
                "enroll-status",
            "pairingId":
                "pairing-status",
        }
    )

    _run(handler)

    assert handler.response_status == 200

    response = repr(
        handler.response_payload
    )

    for forbidden in (
        "publicKey",
        "public_key",
        "Capability",
        "capability",
        "peerBaseUrl",
        "peer_base_url",
    ):
        assert forbidden not in response
