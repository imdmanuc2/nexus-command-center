import io
import json

from backend.api import nexus_peer_server


PATH = "/api/nexus/enrollment/request"


class FakeHeaders(dict):
    def get_all(self, name):
        values = [
            value
            for key, value in self.items()
            if key.lower() == name.lower()
        ]
        return values or None


class FakeHandler:
    def __init__(self, *, body, headers=None):
        self.path = PATH
        self.headers = FakeHeaders(
            headers or {}
        )
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self.response_status = None
        self.response_headers = {}

    def send_response(self, status):
        self.response_status = status

    def send_header(self, name, value):
        self.response_headers[name] = value

    def end_headers(self):
        pass

    def _send_json(self, payload, status=200):
        self.response_status = status
        self.response_payload = payload

    def _read_json_body(self):
        length = int(
            self.headers.get(
                "Content-Length",
                "0",
            )
        )

        body = self.rfile.read(length)
        self._test_raw_body = body

        return (
            json.loads(
                body.decode("utf-8")
            ),
            body,
        )


def _body():
    return json.dumps(
        {
            "remoteInstanceId": "nexus-remote",
            "remoteName": "Remote Nexus",
            "remoteHostname": "remote",
            "peerBaseUrl": "http://remote:8561",
            "publicKeyAlgorithm": "Ed25519",
            "publicKey": "example",
            "publicKeyFingerprint": "sha256:example",
        }
    ).encode("utf-8")


def _invoke(handler):
    nexus_peer_server.NexusPeerHandler.do_POST(
        handler
    )


def test_authentication_occurs_before_enrollment_creation(
    monkeypatch,
):
    events = []

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_auth_service,
        "authenticate_enrollment_request",
        lambda **kwargs: events.append("auth")
        or {
            "authenticated": True,
            "remoteInstanceId": "nexus-remote",
        },
    )

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_service,
        "create_remote_pairing_request",
        lambda **kwargs: events.append("create")
        or {
            "status": "ok",
            "enrollment": {
                "enrollmentId": "enroll-test",
            },
            "enrollmentSecret": "internal-test-secret",
        },
    )

    body = _body()
    handler = FakeHandler(
        body=body,
        headers={
            "Content-Length": str(len(body)),
        },
    )

    _invoke(handler)

    assert events == ["auth", "create"]
    assert handler.response_status == 201


def test_failed_authentication_never_creates_enrollment(
    monkeypatch,
):
    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_auth_service,
        "authenticate_enrollment_request",
        lambda **kwargs: (_ for _ in ()).throw(
            PermissionError("invalid signature")
        ),
    )

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_service,
        "create_remote_pairing_request",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError(
                "unauthenticated request created enrollment"
            )
        ),
    )

    body = _body()
    handler = FakeHandler(
        body=body,
        headers={
            "Content-Length": str(len(body)),
        },
    )

    _invoke(handler)

    assert handler.response_status in {
        400,
        401,
        403,
    }


def test_authenticator_receives_exact_raw_body(
    monkeypatch,
):
    captured = {}

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_auth_service,
        "authenticate_enrollment_request",
        lambda **kwargs: captured.update(kwargs)
        or {
            "authenticated": True,
        },
    )

    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_service,
        "create_remote_pairing_request",
        lambda **kwargs: {
            "status": "ok",
            "enrollment": {
                "enrollmentId": "enroll-test",
            },
            "enrollmentSecret": "internal-test-secret",
        },
    )

    body = _body()
    handler = FakeHandler(
        body=body,
        headers={
            "Content-Length": str(len(body)),
        },
    )

    _invoke(handler)

    assert captured["body"] == body
    assert captured["method"] == "POST"
    assert captured["path"] == PATH
    assert captured["payload"] == json.loads(
        body.decode("utf-8")
    )


def test_auth_failure_response_does_not_echo_secret(
    monkeypatch,
):
    monkeypatch.setattr(
        nexus_peer_server
        .nexus_peer_enrollment_auth_service,
        "authenticate_enrollment_request",
        lambda **kwargs: (_ for _ in ()).throw(
            PermissionError(
                "secret-value-that-must-not-escape"
            )
        ),
    )

    body = _body()
    handler = FakeHandler(
        body=body,
        headers={
            "Content-Length": str(len(body)),
        },
    )

    _invoke(handler)

    encoded = json.dumps(
        getattr(
            handler,
            "response_payload",
            {},
        )
    )

    assert (
        "secret-value-that-must-not-escape"
        not in encoded
    )
