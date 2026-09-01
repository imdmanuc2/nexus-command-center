import hashlib
import json
from datetime import datetime, timezone

import pytest

from backend.services import (
    nexus_peer_enrollment_client_service as client,
)
from backend.services import (
    nexus_peer_enrollment_service as enrollment,
)


CAPABILITY = "test-capability-owned-by-initiator"
CAPABILITY_HASH = hashlib.sha256(
    CAPABILITY.encode("utf-8")
).hexdigest()


def _machine():
    return {
        "algorithm": "Ed25519",
        "publicKey": "test-public-key",
        "fingerprint": "sha256:test",
    }


def test_client_payload_contains_hash_not_capability(
    monkeypatch,
):
    monkeypatch.setattr(
        client,
        "_local_instance",
        lambda: {
            "instanceId": "nexus-local",
            "name": "Local Nexus",
            "hostname": "local",
        },
    )

    monkeypatch.setattr(
        client.nexus_peer_machine_identity_service,
        "local_public_identity",
        _machine,
    )

    monkeypatch.setattr(
        client.nexus_peer_machine_identity_service,
        "decode_public_key",
        lambda value: b"key",
    )

    monkeypatch.setattr(
        client.nexus_peer_machine_identity_service,
        "public_key_fingerprint",
        lambda value: "sha256:test",
    )

    monkeypatch.setattr(
        client.nexus_peer_request_auth_service,
        "sign_request",
        lambda **kwargs: {
            "protocol": "nexus-peer-auth-v1",
            "algorithm": "Ed25519",
            "senderInstanceId": "nexus-local",
            "targetInstanceId": "nexus-remote",
            "timestamp": "2026-09-01T00:00:00Z",
            "nonce": "n" * 32,
            "bodySha256": hashlib.sha256(
                kwargs["body"]
            ).hexdigest(),
            "signature": "signature",
        },
    )

    result = client.build_signed_enrollment_request(
        remote_instance_id="nexus-remote",
        peer_base_url="http://remote:8561",
        local_peer_base_url="http://local:8561",
        pairing_id="pairing-test",
        capability_hash=CAPABILITY_HASH,
        timestamp=datetime(
            2026,
            9,
            1,
            tzinfo=timezone.utc,
        ),
        nonce="n" * 32,
    )

    payload = json.loads(
        result["body"].decode("utf-8")
    )

    assert payload["pairingId"] == "pairing-test"
    assert payload["capabilityHash"] == CAPABILITY_HASH
    assert "enrollmentSecret" not in payload
    assert CAPABILITY not in result["body"].decode(
        "utf-8"
    )


def test_receiver_exact_retry_returns_same_enrollment(
    monkeypatch,
):
    settings = {
        "instance_id": "nexus-receiver",
        "allow_peer_connections": True,
    }

    stored = {}

    monkeypatch.setattr(
        enrollment,
        "_require_connections_enabled",
        lambda: settings,
    )

    def create_enrollment_idempotent(**kwargs):
        if stored:
            return dict(stored)

        stored.update(
            {
                "enrollment_id": kwargs["enrollment_id"],
                "local_instance_id":
                    kwargs["local_instance_id"],
                "secret_hash":
                    kwargs["secret_hash"],
                "status": "pending",
                "requested_remote_instance_id":
                    kwargs[
                        "requested_remote_instance_id"
                    ],
                "requested_remote_name":
                    kwargs["requested_remote_name"],
                "requested_remote_hostname":
                    kwargs[
                        "requested_remote_hostname"
                    ],
                "requested_peer_base_url":
                    kwargs["requested_peer_base_url"],
                "requested_public_key_algorithm":
                    "",
                "requested_public_key": "",
                "requested_public_key_fingerprint":
                    "",
                "request_id":
                    kwargs["request_id"],
                "expires_at":
                    kwargs["expires_at"],
                "approved_at": None,
                "rejected_at": None,
                "used_at": None,
                "created_at":
                    kwargs["expires_at"],
                "updated_at":
                    kwargs["expires_at"],
            }
        )

        return dict(stored)

    monkeypatch.setattr(
        enrollment.nexus_peer_enrollment_repository,
        "create_enrollment_idempotent",
        create_enrollment_idempotent,
    )

    kwargs = {
        "remote_instance_id": "nexus-requester",
        "remote_name": "Requester",
        "remote_hostname": "requester",
        "peer_base_url":
            "http://requester:8561",
        "pairing_id": "pairing-test",
        "capability_hash": CAPABILITY_HASH,
    }

    first = enrollment.create_remote_pairing_request(
        **kwargs
    )

    second = enrollment.create_remote_pairing_request(
        **kwargs
    )

    assert first["created"] is True
    assert second["created"] is False

    assert (
        first["enrollment"]["enrollmentId"]
        == second["enrollment"]["enrollmentId"]
    )

    assert (
        first["enrollment"]["enrollmentId"]
        == stored["enrollment_id"]
    )

    assert (
        first["enrollment"]["enrollmentId"]
        .startswith("enroll-")
    )

    assert "enrollmentSecret" not in first
    assert "enrollmentSecret" not in second


def test_receiver_conflicting_retry_is_rejected(
    monkeypatch,
):
    settings = {
        "instance_id": "nexus-receiver",
        "allow_peer_connections": True,
    }

    monkeypatch.setattr(
        enrollment,
        "_require_connections_enabled",
        lambda: settings,
    )

    monkeypatch.setattr(
        enrollment.nexus_peer_enrollment_repository,
        "create_enrollment_idempotent",
        lambda **kwargs: {
            "enrollment_id": "enroll-test",
            "local_instance_id": "nexus-receiver",
            "secret_hash": "0" * 64,
            "status": "pending",
            "requested_remote_instance_id":
                "nexus-requester",
            "requested_remote_name": "Requester",
            "requested_remote_hostname": "requester",
            "requested_peer_base_url":
                "http://requester:8561",
            "requested_public_key_algorithm": "",
            "requested_public_key": "",
            "requested_public_key_fingerprint": "",
            "request_id": "pairing-test",
            "expires_at": datetime.now(
                timezone.utc
            ),
            "approved_at": None,
            "rejected_at": None,
            "used_at": None,
            "created_at": datetime.now(
                timezone.utc
            ),
            "updated_at": datetime.now(
                timezone.utc
            ),
        },
    )

    with pytest.raises(
        PermissionError,
        match="conflicts",
    ):
        enrollment.create_remote_pairing_request(
            remote_instance_id="nexus-requester",
            remote_name="Requester",
            remote_hostname="requester",
            peer_base_url="http://requester:8561",
            pairing_id="pairing-test",
            capability_hash=CAPABILITY_HASH,
        )


def test_receiver_never_generates_remote_secret():
    import inspect

    source = inspect.getsource(
        enrollment.create_remote_pairing_request
    )

    assert "token_urlsafe" not in source
    assert "enrollmentSecret" not in source
