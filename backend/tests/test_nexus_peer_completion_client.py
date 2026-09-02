"""Tests for initiator-side signed enrollment completion transport."""

import json
from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.services import (
    nexus_peer_enrollment_client_service
    as client,
)


LOCAL = "nexus-local"
REMOTE = "nexus-remote"
PAIRING = "pairing-test"
ENROLLMENT = "enrollment-test"
CAPABILITY = "synthetic-one-time-capability"


class FakeResponse:
    def __init__(
        self,
        *,
        status=200,
        payload=None,
    ):
        self.status = status
        self.payload = (
            payload
            if payload is not None
            else {
                "status": "connected",
                "enrollmentId": ENROLLMENT,
                "pairingId": PAIRING,
                "localInstanceId": REMOTE,
                "remoteInstanceId": LOCAL,
                "peerId": "peer-" + LOCAL,
                "created": True,
            }
        )

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
        return json.dumps(
            self.payload,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")


@pytest.fixture(autouse=True)
def local_instance(monkeypatch):
    monkeypatch.setattr(
        client,
        "_local_instance",
        lambda: {
            "instanceId": LOCAL,
            "name": "Local Nexus",
            "hostname": "local",
        },
    )


def test_completion_url_is_dedicated():
    assert (
        client.enrollment_completion_url(
            "http://remote.example:8561"
        )
        == (
            "http://remote.example:8561"
            "/api/nexus/enrollment/complete"
        )
    )

    assert (
        client.ENROLLMENT_COMPLETE_PATH
        != client.ENROLLMENT_REQUEST_PATH
    )


def test_builder_contains_only_completion_payload_fields(
    monkeypatch,
):
    captured = {}

    def sign_request(**kwargs):
        captured.update(kwargs)

        return {
            "protocol": "nexus-peer-auth-v1",
            "algorithm": "Ed25519",
            "senderInstanceId": LOCAL,
            "targetInstanceId": REMOTE,
            "timestamp":
                "2026-09-01T00:00:00+00:00",
            "nonce": "n" * 32,
            "bodySha256": "a" * 64,
            "signature": "synthetic-signature",
        }

    monkeypatch.setattr(
        client.nexus_peer_request_auth_service,
        "sign_request",
        sign_request,
    )

    result = (
        client.build_signed_enrollment_completion(
            remote_instance_id=REMOTE,
            peer_base_url=(
                "http://remote.example:8561"
            ),
            enrollment_id=ENROLLMENT,
            pairing_id=PAIRING,
            enrollment_capability=CAPABILITY,
            timestamp=datetime(
                2026,
                9,
                1,
                tzinfo=timezone.utc,
            ),
            nonce="n" * 32,
        )
    )

    assert set(
        result["payload"]
    ) == {
        "enrollmentId",
        "pairingId",
        "enrollmentCapability",
    }

    assert result["payload"] == {
        "enrollmentId": ENROLLMENT,
        "pairingId": PAIRING,
        "enrollmentCapability": CAPABILITY,
    }

    encoded = json.loads(
        result["body"].decode("utf-8")
    )

    assert encoded == result["payload"]

    assert "publicKey" not in encoded
    assert "publicKeyFingerprint" not in encoded
    assert "capabilityHash" not in encoded
    assert "token" not in encoded

    assert captured["method"] == "POST"
    assert (
        captured["path"]
        == client.ENROLLMENT_COMPLETE_PATH
    )
    assert (
        captured["sender_instance_id"]
        == LOCAL
    )
    assert (
        captured["target_instance_id"]
        == REMOTE
    )
    assert captured["body"] == result["body"]


def test_transport_validates_success_identity(
    monkeypatch,
):
    monkeypatch.setattr(
        client.nexus_peer_request_auth_service,
        "sign_request",
        lambda **kwargs: {
            "protocol": "nexus-peer-auth-v1",
            "algorithm": "Ed25519",
            "senderInstanceId": LOCAL,
            "targetInstanceId": REMOTE,
            "timestamp":
                "2026-09-01T00:00:00+00:00",
            "nonce": "n" * 32,
            "bodySha256": "a" * 64,
            "signature": "synthetic-signature",
        },
    )

    captured = {}

    def opener(
        request,
        timeout,
    ):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    result = (
        client.complete_remote_enrollment_request(
            remote_instance_id=REMOTE,
            peer_base_url=(
                "http://remote.example:8561"
            ),
            enrollment_id=ENROLLMENT,
            pairing_id=PAIRING,
            enrollment_capability=CAPABILITY,
            opener=opener,
        )
    )

    assert result == {
        "status": "connected",
        "enrollmentId": ENROLLMENT,
        "pairingId": PAIRING,
        "localInstanceId": REMOTE,
        "remoteInstanceId": LOCAL,
        "peerId": "peer-" + LOCAL,
        "created": True,
    }

    request = captured["request"]

    assert (
        request.full_url
        == (
            "http://remote.example:8561"
            "/api/nexus/enrollment/complete"
        )
    )

    sent = json.loads(
        request.data.decode("utf-8")
    )

    assert sent[
        "enrollmentCapability"
    ] == CAPABILITY


@pytest.mark.parametrize(
    "field,value",
    [
        (
            "enrollmentId",
            "wrong-enrollment",
        ),
        (
            "pairingId",
            "wrong-pairing",
        ),
        (
            "localInstanceId",
            "wrong-remote",
        ),
        (
            "remoteInstanceId",
            "wrong-local",
        ),
        (
            "peerId",
            "wrong-peer",
        ),
    ],
)
def test_transport_rejects_identity_mismatch(
    monkeypatch,
    field,
    value,
):
    monkeypatch.setattr(
        client.nexus_peer_request_auth_service,
        "sign_request",
        lambda **kwargs: {
            "protocol": "nexus-peer-auth-v1",
            "algorithm": "Ed25519",
            "senderInstanceId": LOCAL,
            "targetInstanceId": REMOTE,
            "timestamp":
                "2026-09-01T00:00:00+00:00",
            "nonce": "n" * 32,
            "bodySha256": "a" * 64,
            "signature": "synthetic-signature",
        },
    )

    payload = {
        "status": "connected",
        "enrollmentId": ENROLLMENT,
        "pairingId": PAIRING,
        "localInstanceId": REMOTE,
        "remoteInstanceId": LOCAL,
        "peerId": "peer-" + LOCAL,
        "created": False,
    }

    payload[field] = value

    with pytest.raises(
        RuntimeError,
    ):
        client.complete_remote_enrollment_request(
            remote_instance_id=REMOTE,
            peer_base_url=(
                "http://remote.example:8561"
            ),
            enrollment_id=ENROLLMENT,
            pairing_id=PAIRING,
            enrollment_capability=CAPABILITY,
            opener=lambda *args, **kwargs:
                FakeResponse(
                    payload=payload
                ),
        )


def test_idempotent_receiver_success_is_accepted(
    monkeypatch,
):
    monkeypatch.setattr(
        client.nexus_peer_request_auth_service,
        "sign_request",
        lambda **kwargs: {
            "protocol": "nexus-peer-auth-v1",
            "algorithm": "Ed25519",
            "senderInstanceId": LOCAL,
            "targetInstanceId": REMOTE,
            "timestamp":
                "2026-09-01T00:00:00+00:00",
            "nonce": "fresh-nonce",
            "bodySha256": "a" * 64,
            "signature": "synthetic-signature",
        },
    )

    result = (
        client.complete_remote_enrollment_request(
            remote_instance_id=REMOTE,
            peer_base_url=(
                "http://remote.example:8561"
            ),
            enrollment_id=ENROLLMENT,
            pairing_id=PAIRING,
            enrollment_capability=CAPABILITY,
            opener=lambda *args, **kwargs:
                FakeResponse(
                    payload={
                        "status": "connected",
                        "enrollmentId":
                            ENROLLMENT,
                        "pairingId":
                            PAIRING,
                        "localInstanceId":
                            REMOTE,
                        "remoteInstanceId":
                            LOCAL,
                        "peerId":
                            "peer-" + LOCAL,
                        "created":
                            False,
                    }
                ),
        )
    )

    assert result["status"] == "connected"
    assert result["created"] is False


def test_transport_does_not_touch_pairing_state_or_credentials():
    text = (
        __import__(
            "pathlib"
        )
        .Path(
            "backend/services/"
            "nexus_peer_enrollment_client_service.py"
        )
        .read_text(
            encoding="utf-8"
        )
    )

    function = text.split(
        "def complete_remote_enrollment_request(",
        1,
    )[1]

    assert (
        "nexus_peer_outbound_pairing_repository"
        not in function
    )

    assert (
        "nexus_peer_pairing_credential_service"
        not in function
    )

    assert "delete_credential" not in function
    assert "register_verified_peer" not in function
