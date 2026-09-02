"""HTTP contract tests for signed Nexus enrollment completion."""

import io
import json

from backend.api import (
    nexus_peer_server,
)


PATH = (
    "/api/nexus/enrollment/complete"
)

CAPABILITY = (
    "synthetic-completion-capability"
)


class FakeHeaders(dict):
    def get_all(self, name):
        values = [
            value
            for key, value
            in self.items()
            if key.lower()
            == name.lower()
        ]

        return values or None


class FakeHandler:
    def __init__(
        self,
        *,
        body,
        path=PATH,
        headers=None,
    ):
        self.path = path

        self.headers = FakeHeaders(
            headers or {}
        )

        self.headers.setdefault(
            "Content-Length",
            str(len(body)),
        )

        self.rfile = io.BytesIO(
            body
        )

        self.wfile = io.BytesIO()

        self.response_status = None
        self.response_payload = None

    def send_response(
        self,
        status,
    ):
        self.response_status = status

    def send_header(
        self,
        name,
        value,
    ):
        pass

    def end_headers(self):
        pass

    def _send_json(
        self,
        payload,
        status=200,
    ):
        self.response_status = status
        self.response_payload = payload

    def _read_json_body(self):
        return (
            nexus_peer_server
            .NexusPeerHandler
            ._read_json_body(self)
        )


def _payload():
    return {
        "enrollmentId":
            "enroll-body",
        "pairingId":
            "pairing-body",
        "enrollmentCapability":
            CAPABILITY,
    }


def _body(
    payload=None,
):
    return json.dumps(
        (
            _payload()
            if payload is None
            else payload
        ),
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _invoke(handler):
    (
        nexus_peer_server
        .NexusPeerHandler
        .do_POST(handler)
    )


def _auth_result():
    return {
        "authenticated":
            True,
        "localInstanceId":
            "nexus-local",
        "remoteInstanceId":
            "nexus-authenticated-remote",
        "enrollmentId":
            "enroll-authenticated",
        "pairingId":
            "pairing-authenticated",
        "publicKeyFingerprint":
            "sha256:synthetic",
    }


def _success():
    return {
        "status":
            "connected",
        "enrollmentId":
            "enroll-authenticated",
        "pairingId":
            "pairing-authenticated",
        "localInstanceId":
            "nexus-local",
        "remoteInstanceId":
            "nexus-authenticated-remote",
        "peerId":
            "peer-nexus-authenticated-remote",
        "created":
            True,
    }


def test_completion_route_is_signed_and_legacy_consume_is_retired():
    assert (
        nexus_peer_server
        .ENROLLMENT_COMPLETE_PATH
        == PATH
    )

    assert (
        PATH
        == "/api/nexus/enrollment/complete"
    )

    assert not hasattr(
        nexus_peer_server,
        "ENROLLMENT_CONSUME_PATH",
    )


def test_authentication_occurs_before_completion(
    monkeypatch,
):
    events = []

    def authenticate(**kwargs):
        events.append("auth")
        return _auth_result()

    def complete(**kwargs):
        events.append("complete")
        return _success()

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_auth_service,
        "authenticate_enrollment_completion",
        authenticate,
    )

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_service,
        "complete_remote_enrollment",
        complete,
    )

    handler = FakeHandler(
        body=_body()
    )

    _invoke(handler)

    assert events == [
        "auth",
        "complete",
    ]

    assert (
        handler.response_status
        == 200
    )


def test_authenticator_receives_exact_raw_body(
    monkeypatch,
):
    captured = {}

    body = _body()

    def authenticate(**kwargs):
        captured.update(kwargs)
        return _auth_result()

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_auth_service,
        "authenticate_enrollment_completion",
        authenticate,
    )

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_service,
        "complete_remote_enrollment",
        lambda **kwargs: _success(),
    )

    handler = FakeHandler(
        body=body
    )

    _invoke(handler)

    assert captured["method"] == "POST"
    assert captured["path"] == PATH
    assert captured["body"] == body

    assert captured["payload"] == (
        json.loads(
            body.decode("utf-8")
        )
    )

    assert (
        captured["headers"]
        is handler.headers
    )


def test_service_identity_comes_from_authentication(
    monkeypatch,
):
    captured = {}

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_auth_service,
        "authenticate_enrollment_completion",
        lambda **kwargs:
            _auth_result(),
    )

    def complete(**kwargs):
        captured.update(kwargs)
        return _success()

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_service,
        "complete_remote_enrollment",
        complete,
    )

    handler = FakeHandler(
        body=_body()
    )

    _invoke(handler)

    assert captured == {
        "enrollment_id":
            "enroll-authenticated",
        "pairing_id":
            "pairing-authenticated",
        "authenticated_remote_instance_id":
            "nexus-authenticated-remote",
        "enrollment_secret":
            CAPABILITY,
    }


def test_auth_failure_never_calls_completion(
    monkeypatch,
):
    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_auth_service,
        "authenticate_enrollment_completion",
        lambda **kwargs:
            (_ for _ in ()).throw(
                PermissionError(
                    "sensitive-internal-auth-detail"
                )
            ),
    )

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_service,
        "complete_remote_enrollment",
        lambda **kwargs:
            (_ for _ in ()).throw(
                AssertionError(
                    "completion must not run"
                )
            ),
    )

    handler = FakeHandler(
        body=_body()
    )

    _invoke(handler)

    assert (
        handler.response_status
        == 403
    )

    assert handler.response_payload == {
        "status":
            "error",
        "error":
            "enrollment_completion_authentication_failed",
    }

    encoded = json.dumps(
        handler.response_payload
    )

    assert (
        "sensitive-internal-auth-detail"
        not in encoded
    )


def test_completion_permission_failure_is_fixed_and_secret_free(
    monkeypatch,
):
    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_auth_service,
        "authenticate_enrollment_completion",
        lambda **kwargs:
            _auth_result(),
    )

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_service,
        "complete_remote_enrollment",
        lambda **kwargs:
            (_ for _ in ()).throw(
                PermissionError(
                    "capability-secret-must-not-escape"
                )
            ),
    )

    handler = FakeHandler(
        body=_body()
    )

    _invoke(handler)

    assert (
        handler.response_status
        == 403
    )

    assert handler.response_payload == {
        "status":
            "error",
        "error":
            "enrollment_completion_failed",
    }

    assert (
        "capability-secret-must-not-escape"
        not in json.dumps(
            handler.response_payload
        )
    )


def test_malformed_json_returns_fixed_error(
    monkeypatch,
):
    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_auth_service,
        "authenticate_enrollment_completion",
        lambda **kwargs:
            (_ for _ in ()).throw(
                AssertionError(
                    "malformed body must not authenticate"
                )
            ),
    )

    handler = FakeHandler(
        body=b"{not-json"
    )

    _invoke(handler)

    assert (
        handler.response_status
        == 400
    )

    assert handler.response_payload == {
        "status":
            "error",
        "error":
            "invalid_enrollment_completion_request",
    }


def test_unexpected_field_never_authenticates(
    monkeypatch,
):
    called = {
        "auth": False,
    }

    def authenticate(**kwargs):
        called["auth"] = True
        raise AssertionError(
            "unexpected field reached authenticator"
        )

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_auth_service,
        "authenticate_enrollment_completion",
        authenticate,
    )

    payload = {
        **_payload(),
        "publicKey":
            "attacker-key",
    }

    handler = FakeHandler(
        body=_body(payload)
    )

    _invoke(handler)

    assert (
        handler.response_status
        == 400
    )

    assert called["auth"] is False

    assert handler.response_payload == {
        "status":
            "error",
        "error":
            "invalid_enrollment_completion_request",
    }


def test_success_response_contains_no_secret_material(
    monkeypatch,
):
    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_auth_service,
        "authenticate_enrollment_completion",
        lambda **kwargs:
            _auth_result(),
    )

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_service,
        "complete_remote_enrollment",
        lambda **kwargs:
            _success(),
    )

    handler = FakeHandler(
        body=_body()
    )

    _invoke(handler)

    assert (
        handler.response_status
        == 200
    )

    encoded = json.dumps(
        handler.response_payload
    )

    forbidden = (
        CAPABILITY,
        "capabilityHash",
        "enrollmentCapability",
        "publicKey",
        "publicKeyFingerprint",
        "bearer",
        "token",
    )

    for value in forbidden:
        assert value not in encoded


def test_legacy_consume_service_not_used_by_completion(
    monkeypatch,
):
    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_auth_service,
        "authenticate_enrollment_completion",
        lambda **kwargs:
            _auth_result(),
    )

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_service,
        "complete_remote_enrollment",
        lambda **kwargs:
            _success(),
    )

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_service,
        "consume_enrollment",
        lambda **kwargs:
            (_ for _ in ()).throw(
                AssertionError(
                    "legacy consume route was reused"
                )
            ),
    )

    handler = FakeHandler(
        body=_body()
    )

    _invoke(handler)

    assert (
        handler.response_status
        == 200
    )
