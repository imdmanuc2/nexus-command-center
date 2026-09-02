"""Tests for signed initiator enrollment status transport."""

import json
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from backend.services import (
    nexus_peer_enrollment_client_service as client,
)
from backend.services import (
    nexus_peer_request_auth_service as request_auth,
)


REMOTE = "nexus-remote"
LOCAL = "nexus-local"
ENROLLMENT = "enroll-status"
PAIRING = "pairing-status"
BASE_URL = "http://10.0.0.20:8561"
PATH = "/api/nexus/enrollment/status"
NOW = datetime(
    2026,
    9,
    2,
    16,
    0,
    tzinfo=timezone.utc,
)


class Response:
    def __init__(
        self,
        payload,
        status=200,
    ):
        self._raw = json.dumps(
            payload,
            separators=(",", ":"),
        ).encode("utf-8")
        self._status = status

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        tb,
    ):
        return False

    def getcode(self):
        return self._status

    def read(self, size=-1):
        return self._raw[:size]


def _local(monkeypatch):
    monkeypatch.setattr(
        client,
        "_local_instance",
        lambda: {
            "instanceId": LOCAL,
            "name": "Local Nexus",
            "hostname": "local",
        },
    )


def _response(
    *,
    enrollment_id=ENROLLMENT,
    pairing_id=PAIRING,
    local_instance_id=REMOTE,
    remote_instance_id=LOCAL,
    enrollment_status="pending",
):
    return {
        "status": "ok",
        "enrollmentId": enrollment_id,
        "pairingId": pairing_id,
        "localInstanceId": local_instance_id,
        "remoteInstanceId": remote_instance_id,
        "enrollmentStatus": enrollment_status,
        "expiresAt":
            "2026-09-02T18:00:00+00:00",
    }


def test_status_path_and_url_are_canonical(monkeypatch):
    _local(monkeypatch)

    assert (
        client.ENROLLMENT_STATUS_PATH
        == PATH
    )

    assert (
        client.enrollment_status_url(
            BASE_URL
        )
        == BASE_URL + PATH
    )


def test_signed_status_body_contains_only_pairing_identity(
    monkeypatch,
):
    _local(monkeypatch)

    result = (
        client.build_signed_enrollment_status(
            remote_instance_id=REMOTE,
            peer_base_url=BASE_URL,
            enrollment_id=ENROLLMENT,
            pairing_id=PAIRING,
            timestamp=NOW,
        )
    )

    assert result["method"] == "POST"
    assert result["path"] == PATH

    payload = json.loads(
        result["body"].decode("utf-8")
    )

    assert payload == {
        "enrollmentId": ENROLLMENT,
        "pairingId": PAIRING,
    }

    forbidden = {
        "publicKey",
        "publicKeyFingerprint",
        "publicKeyAlgorithm",
        "remoteInstanceId",
        "enrollmentCapability",
        "capabilityHash",
    }

    assert not (
        set(payload)
        & forbidden
    )

    assert set(
        result["headers"]
    ) == set(
        request_auth.AUTH_HEADERS
    )


@pytest.mark.parametrize(
    "state",
    [
        "pending",
        "approved",
        "rejected",
        "expired",
        "used",
    ],
)
def test_status_transport_accepts_only_known_lifecycle_states(
    monkeypatch,
    state,
):
    _local(monkeypatch)

    opener = Mock(
        return_value=Response(
            _response(
                enrollment_status=state,
            )
        )
    )

    result = (
        client.request_remote_enrollment_status(
            remote_instance_id=REMOTE,
            peer_base_url=BASE_URL,
            enrollment_id=ENROLLMENT,
            pairing_id=PAIRING,
            timestamp=NOW,
            opener=opener,
        )
    )

    assert result["status"] == "ok"
    assert (
        result["enrollmentStatus"]
        == state
    )

    assert result["enrollmentId"] == ENROLLMENT
    assert result["pairingId"] == PAIRING
    assert result["localInstanceId"] == REMOTE
    assert result["remoteInstanceId"] == LOCAL

    assert opener.call_count == 1


@pytest.mark.parametrize(
    "field,value,error",
    [
        (
            "enrollment_id",
            "wrong-enrollment",
            "enrollmentId mismatch",
        ),
        (
            "pairing_id",
            "wrong-pairing",
            "pairingId mismatch",
        ),
        (
            "local_instance_id",
            "wrong-receiver",
            "wrong Nexus",
        ),
        (
            "remote_instance_id",
            "wrong-requester",
            "wrong requester",
        ),
    ],
)
def test_status_transport_rejects_identity_mismatch(
    monkeypatch,
    field,
    value,
    error,
):
    _local(monkeypatch)

    kwargs = {
        "enrollment_id":
            ENROLLMENT,
        "pairing_id":
            PAIRING,
        "local_instance_id":
            REMOTE,
        "remote_instance_id":
            LOCAL,
    }

    kwargs[field] = value

    opener = Mock(
        return_value=Response(
            _response(**kwargs)
        )
    )

    with pytest.raises(
        RuntimeError,
        match=error,
    ):
        client.request_remote_enrollment_status(
            remote_instance_id=REMOTE,
            peer_base_url=BASE_URL,
            enrollment_id=ENROLLMENT,
            pairing_id=PAIRING,
            timestamp=NOW,
            opener=opener,
        )


def test_status_transport_rejects_unknown_state(
    monkeypatch,
):
    _local(monkeypatch)

    opener = Mock(
        return_value=Response(
            _response(
                enrollment_status=
                    "unexpected-state",
            )
        )
    )

    with pytest.raises(
        RuntimeError,
        match="invalid lifecycle state",
    ):
        client.request_remote_enrollment_status(
            remote_instance_id=REMOTE,
            peer_base_url=BASE_URL,
            enrollment_id=ENROLLMENT,
            pairing_id=PAIRING,
            timestamp=NOW,
            opener=opener,
        )


def test_status_transport_performs_no_pairing_mutation(
    monkeypatch,
):
    _local(monkeypatch)

    opener = Mock(
        return_value=Response(
            _response(
                enrollment_status="approved",
            )
        )
    )

    result = (
        client.request_remote_enrollment_status(
            remote_instance_id=REMOTE,
            peer_base_url=BASE_URL,
            enrollment_id=ENROLLMENT,
            pairing_id=PAIRING,
            timestamp=NOW,
            opener=opener,
        )
    )

    assert result[
        "enrollmentStatus"
    ] == "approved"

    source = (
        client
        .request_remote_enrollment_status
        .__code__
        .co_names
    )

    assert (
        "transition_pairing"
        not in source
    )

    assert (
        "complete_pairing"
        not in source
    )


def test_status_builder_signs_exact_status_path(
    monkeypatch,
):
    _local(monkeypatch)

    captured = {}

    def sign_request(**kwargs):
        captured.update(kwargs)

        return {
            "protocol":
                "nexus-peer-auth-v1",
            "algorithm":
                "Ed25519",
            "senderInstanceId":
                LOCAL,
            "targetInstanceId":
                REMOTE,
            "timestamp":
                "2026-09-02T16:00:00Z",
            "nonce":
                "a" * 43,
            "bodySha256":
                "b" * 64,
            "signature":
                "c" * 86,
        }

    monkeypatch.setattr(
        client.nexus_peer_request_auth_service,
        "sign_request",
        sign_request,
    )

    client.build_signed_enrollment_status(
        remote_instance_id=REMOTE,
        peer_base_url=BASE_URL,
        enrollment_id=ENROLLMENT,
        pairing_id=PAIRING,
        timestamp=NOW,
    )

    assert captured["method"] == "POST"
    assert captured["path"] == PATH
    assert (
        captured["sender_instance_id"]
        == LOCAL
    )
    assert (
        captured["target_instance_id"]
        == REMOTE
    )
