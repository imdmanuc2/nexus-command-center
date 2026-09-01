import json
from datetime import datetime, timezone

import pytest

from backend.services import (
    nexus_peer_enrollment_client_service as service,
)
from backend.services import (
    nexus_peer_machine_identity_service as machine_service,
)
from backend.services import (
    nexus_peer_request_auth_service as auth_service,
)


class FakeResponse:
    def __init__(
        self,
        payload,
        *,
        status=201,
    ):
        self.status = status
        self.raw = json.dumps(
            payload,
            separators=(",", ":"),
        ).encode("utf-8")

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
        return self.raw[:size]


@pytest.fixture
def identities(
    monkeypatch,
):
    local_key = (
        machine_service
        .generate_private_key()
    )

    local_identity = (
        machine_service
        .public_identity_from_private_key(
            local_key
        )
    )

    remote_key = (
        machine_service
        .generate_private_key()
    )

    remote_identity = (
        machine_service
        .public_identity_from_private_key(
            remote_key
        )
    )

    monkeypatch.setattr(
        service.nexus_instance_service,
        "get_local_instance",
        lambda: {
            "instance_id": "nexus-local",
            "name": "Local Nexus",
            "hostname": "local-host",
        },
    )

    monkeypatch.setattr(
        service.nexus_peer_machine_identity_service,
        "local_public_identity",
        lambda: local_identity,
    )

    monkeypatch.setattr(
        auth_service.nexus_peer_machine_identity_service,
        "sign",
        lambda message: local_key.sign(
            message
        ),
    )

    return {
        "local": local_identity,
        "remote": remote_identity,
    }


def _build(
    identities,
):
    return (
        service.build_signed_enrollment_request(
            remote_instance_id="nexus-remote",
            peer_base_url="http://10.0.0.2:8561",
            local_peer_base_url="http://10.0.0.1:8561",
            timestamp=datetime(
                2026,
                9,
                1,
                12,
                0,
                0,
                tzinfo=timezone.utc,
            ),
            nonce=(
                "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
            ),
        )
    )


def test_builds_exact_receiver_payload(
    identities,
):
    result = _build(
        identities
    )

    assert result["payload"] == {
        "remoteInstanceId": "nexus-local",
        "remoteName": "Local Nexus",
        "remoteHostname": "local-host",
        "peerBaseUrl": "http://10.0.0.1:8561",
        "publicKeyAlgorithm": "Ed25519",
        "publicKey":
            identities["local"]["publicKey"],
        "publicKeyFingerprint":
            identities["local"]["fingerprint"],
    }


def test_signature_covers_exact_transmitted_body(
    identities,
):
    result = _build(
        identities
    )

    assert (
        auth_service.body_sha256(
            result["body"]
        )
        == result["headers"][
            auth_service.HEADER_BODY_SHA256
        ]
    )

    assert auth_service.verify_signature(
        public_key=(
            identities["local"]["publicKey"]
        ),
        protocol=result["headers"][
            auth_service.HEADER_PROTOCOL
        ],
        algorithm=result["headers"][
            auth_service.HEADER_ALGORITHM
        ],
        method=result["method"],
        path=result["path"],
        sender_instance_id=result["headers"][
            auth_service.HEADER_SENDER
        ],
        target_instance_id=result["headers"][
            auth_service.HEADER_TARGET
        ],
        timestamp=result["headers"][
            auth_service.HEADER_TIMESTAMP
        ],
        nonce=result["headers"][
            auth_service.HEADER_NONCE
        ],
        body_sha256_value=result["headers"][
            auth_service.HEADER_BODY_SHA256
        ],
        signature=result["headers"][
            auth_service.HEADER_SIGNATURE
        ],
    )


def test_builder_performs_no_network(
    monkeypatch,
    identities,
):
    monkeypatch.setattr(
        service,
        "urlopen",
        lambda *args, **kwargs: (
            (_ for _ in ()).throw(
                AssertionError(
                    "network must not be touched"
                )
            )
        ),
    )

    _build(
        identities
    )


def test_request_uses_exact_signed_body(
    identities,
):
    captured = {}

    def opener(
        request,
        *,
        timeout,
    ):
        captured["body"] = request.data
        captured["headers"] = dict(
            request.header_items()
        )
        captured["timeout"] = timeout

        return FakeResponse(
            {
                "status": "ok",
                "enrollment": {
                    "enrollmentId": "enroll-test",
                    "localInstanceId":
                        "nexus-remote",
                    "status": "pending",
                    "requestedRemoteInstanceId":
                        "nexus-local",
                    "expiresAt":
                        "2026-09-01T12:15:00Z",
                },
                "enrollmentSecret":
                    "test-secret-not-persisted",
            }
        )

    result = (
        service.request_remote_enrollment(
            remote_instance_id="nexus-remote",
            peer_base_url="http://10.0.0.2:8561",
            local_peer_base_url="http://10.0.0.1:8561",
            opener=opener,
            timestamp=datetime(
                2026,
                9,
                1,
                12,
                0,
                0,
                tzinfo=timezone.utc,
            ),
            nonce=(
                "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
            ),
        )
    )

    body = json.loads(
        captured["body"].decode("utf-8")
    )

    assert body[
        "remoteInstanceId"
    ] == "nexus-local"

    assert captured["headers"][
        "X-nexus-peer-body-sha256"
    ] == auth_service.body_sha256(
        captured["body"]
    )

    assert result == {
        "status": "ok",
        "enrollmentId": "enroll-test",
        "enrollmentStatus": "pending",
        "expiresAt":
            "2026-09-01T12:15:00Z",
        "enrollmentSecret":
            "test-secret-not-persisted",
    }


@pytest.mark.parametrize(
    (
        "mutator",
        "message",
    ),
    [
        (
            lambda payload:
                payload["enrollment"].update(
                    {
                        "status": "approved",
                    }
                ),
            "not pending",
        ),
        (
            lambda payload:
                payload["enrollment"].update(
                    {
                        "requestedRemoteInstanceId":
                            "nexus-other",
                    }
                ),
            "wrong requester",
        ),
        (
            lambda payload:
                payload["enrollment"].update(
                    {
                        "localInstanceId":
                            "nexus-other",
                    }
                ),
            "wrong Nexus",
        ),
        (
            lambda payload:
                payload.pop(
                    "enrollmentSecret"
                ),
            "missing credential",
        ),
    ],
)
def test_rejects_invalid_success_response(
    identities,
    mutator,
    message,
):
    payload = {
        "status": "ok",
        "enrollment": {
            "enrollmentId": "enroll-test",
            "localInstanceId":
                "nexus-remote",
            "status": "pending",
            "requestedRemoteInstanceId":
                "nexus-local",
            "expiresAt":
                "2026-09-01T12:15:00Z",
        },
        "enrollmentSecret":
            "test-secret-not-persisted",
    }

    mutator(
        payload
    )

    def opener(
        request,
        *,
        timeout,
    ):
        return FakeResponse(
            payload
        )

    with pytest.raises(
        RuntimeError,
        match=message,
    ):
        service.request_remote_enrollment(
            remote_instance_id="nexus-remote",
            peer_base_url="http://10.0.0.2:8561",
            local_peer_base_url="http://10.0.0.1:8561",
            opener=opener,
        )


def test_rejects_self_pairing(
    identities,
):
    with pytest.raises(
        ValueError,
        match="local Nexus",
    ):
        service.build_signed_enrollment_request(
            remote_instance_id="nexus-local",
            peer_base_url="http://10.0.0.1:8561",
            local_peer_base_url="http://10.0.0.1:8561",
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
def test_rejects_invalid_timeout(
    identities,
    timeout,
):
    with pytest.raises(
        ValueError,
        match="timeout",
    ):
        service.request_remote_enrollment(
            remote_instance_id="nexus-remote",
            peer_base_url="http://10.0.0.2:8561",
            local_peer_base_url="http://10.0.0.1:8561",
            timeout=timeout,
            opener=lambda *args, **kwargs: (
                (_ for _ in ()).throw(
                    AssertionError(
                        "network must not be touched"
                    )
                )
            ),
        )


def test_public_result_contains_only_expected_secret(
    identities,
):
    def opener(
        request,
        *,
        timeout,
    ):
        return FakeResponse(
            {
                "status": "ok",
                "enrollment": {
                    "enrollmentId": "enroll-test",
                    "localInstanceId":
                        "nexus-remote",
                    "status": "pending",
                    "requestedRemoteInstanceId":
                        "nexus-local",
                    "requestedPeerBaseUrl":
                        "http://should-not-return:8561",
                    "requestedPublicKey":
                        "should-not-return",
                    "expiresAt":
                        "2026-09-01T12:15:00Z",
                },
                "enrollmentSecret":
                    "temporary-secret",
            }
        )

    result = (
        service.request_remote_enrollment(
            remote_instance_id="nexus-remote",
            peer_base_url="http://10.0.0.2:8561",
            local_peer_base_url="http://10.0.0.1:8561",
            opener=opener,
        )
    )

    assert set(result) == {
        "status",
        "enrollmentId",
        "enrollmentStatus",
        "expiresAt",
        "enrollmentSecret",
    }

    assert (
        "requestedPeerBaseUrl"
        not in result
    )

    assert (
        "requestedPublicKey"
        not in result
    )
