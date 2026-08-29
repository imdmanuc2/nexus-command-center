"""Regression tests for Nexus Ed25519 peer identity binding."""

from unittest.mock import patch

import pytest

from backend.services import nexus_peer_enrollment_service as enrollment
from backend.services import nexus_peer_machine_identity_service as machine
from backend.services import nexus_peer_settings_service as settings


def _machine_identity():
    return machine.public_identity_from_private_key(
        machine.generate_private_key()
    )


def _peer_settings():
    return {
        "instance_id": "nexus-local",
        "allow_peer_connections": True,
    }


def _identity_document(machine_identity):
    return {
        "status": "ok",
        "protocol": {
            "name": "seymour-nexus-peer",
            "version": "1",
        },
        "instance": {
            "instanceId": "nexus-remote",
            "organizationId": "",
            "siteId": "",
            "name": "Remote Nexus",
            "hostname": "remote",
            "identitySource": "approved-enrollment",
        },
        "machineIdentity": machine_identity,
        "capabilities": {
            "peerAwareness": True,
            "federation": False,
            "cmdbExchange": False,
            "discoveryExchange": False,
            "management": False,
            "authorityDelegation": False,
        },
    }


def test_enrollment_binds_verified_requester_machine_identity():
    identity = _machine_identity()
    captured = {}

    def fake_create_enrollment(**kwargs):
        captured.update(kwargs)

        return {
            "enrollment_id": kwargs["enrollment_id"],
            "local_instance_id": kwargs["local_instance_id"],
            "requested_remote_instance_id":
                kwargs["requested_remote_instance_id"],
            "requested_remote_name":
                kwargs["requested_remote_name"],
            "requested_remote_hostname":
                kwargs["requested_remote_hostname"],
            "requested_peer_base_url":
                kwargs["requested_peer_base_url"],
            "requested_public_key_algorithm":
                kwargs["requested_public_key_algorithm"],
            "requested_public_key":
                kwargs["requested_public_key"],
            "requested_public_key_fingerprint":
                kwargs["requested_public_key_fingerprint"],
            "status": "pending",
            "expires_at": kwargs["expires_at"],
            "approved_at": None,
            "rejected_at": None,
            "used_at": None,
            "created_at": None,
            "updated_at": None,
        }

    with (
        patch.object(
            enrollment.nexus_peer_repository,
            "get_local_peer_settings",
            return_value=_peer_settings(),
        ),
        patch.object(
            enrollment.nexus_peer_enrollment_repository,
            "create_enrollment",
            side_effect=fake_create_enrollment,
        ),
    ):
        result = enrollment.create_remote_pairing_request(
            remote_instance_id="nexus-remote",
            remote_name="Remote Nexus",
            remote_hostname="remote",
            peer_base_url="http://192.0.2.10:8561",
            public_key_algorithm=identity["algorithm"],
            public_key=identity["publicKey"],
            public_key_fingerprint=identity["fingerprint"],
        )

    assert result["status"] == "ok"
    assert captured[
        "requested_public_key_algorithm"
    ] == "Ed25519"
    assert captured[
        "requested_public_key"
    ] == identity["publicKey"]
    assert captured[
        "requested_public_key_fingerprint"
    ] == identity["fingerprint"]


def test_enrollment_rejects_tampered_fingerprint_before_write():
    identity = _machine_identity()

    with (
        patch.object(
            enrollment.nexus_peer_repository,
            "get_local_peer_settings",
            return_value=_peer_settings(),
        ),
        patch.object(
            enrollment.nexus_peer_enrollment_repository,
            "create_enrollment",
        ) as create_enrollment,
    ):
        with pytest.raises(
            ValueError,
            match="fingerprint",
        ):
            enrollment.create_remote_pairing_request(
                remote_instance_id="nexus-remote",
                remote_name="Remote Nexus",
                remote_hostname="remote",
                peer_base_url="http://192.0.2.10:8561",
                public_key_algorithm="Ed25519",
                public_key=identity["publicKey"],
                public_key_fingerprint=(
                    "sha256:" + ("0" * 64)
                ),
            )

    create_enrollment.assert_not_called()


def test_consumed_enrollment_preserves_machine_identity():
    identity = _machine_identity()

    row = {
        "enrollment_id": "enroll-test",
        "local_instance_id": "nexus-local",
        "requested_remote_instance_id": "nexus-remote",
        "requested_remote_name": "Remote Nexus",
        "requested_remote_hostname": "remote",
        "requested_peer_base_url": "http://192.0.2.10:8561",
        "requested_public_key_algorithm": identity["algorithm"],
        "requested_public_key": identity["publicKey"],
        "requested_public_key_fingerprint": identity["fingerprint"],
        "status": "used",
        "expires_at": None,
        "approved_at": "approved",
        "rejected_at": None,
        "used_at": "used",
        "created_at": None,
        "updated_at": None,
    }

    with (
        patch.object(
            enrollment.nexus_peer_repository,
            "get_local_peer_settings",
            return_value=_peer_settings(),
        ),
        patch.object(
            enrollment.nexus_peer_enrollment_repository,
            "get_enrollment",
            return_value=row,
        ),
        patch.object(
            enrollment.nexus_peer_settings_service,
            "register_verified_peer",
            return_value={
                "status": "ok",
                "peer": {
                    "peerId": "peer-nexus-remote",
                },
            },
        ) as register,
    ):
        result = enrollment.establish_consumed_enrollment_peer(
            enrollment_id="enroll-test"
        )

    assert result["established"] is True

    document = register.call_args.kwargs[
        "identity_document"
    ]

    assert document["machineIdentity"] == identity

    assert document["capabilities"] == {
        "peerAwareness": True,
        "federation": False,
        "cmdbExchange": False,
        "discoveryExchange": False,
        "management": False,
        "authorityDelegation": False,
    }


def test_durable_peer_binds_verified_machine_identity():
    identity = _machine_identity()
    captured = {}

    def fake_upsert(**kwargs):
        captured.update(kwargs)

        return {
            "peer_id": kwargs["peer_id"],
            "remote_instance_id":
                kwargs["remote_instance_id"],
            "organization_id": kwargs["organization_id"],
            "site_id": kwargs["site_id"],
            "name": kwargs["name"],
            "hostname": kwargs["hostname"],
            "peer_base_url": kwargs["peer_base_url"],
            "protocol_name": kwargs["protocol_name"],
            "protocol_version":
                kwargs["protocol_version"],
            "public_key_algorithm":
                kwargs["public_key_algorithm"],
            "public_key": kwargs["public_key"],
            "public_key_fingerprint":
                kwargs["public_key_fingerprint"],
            "status": "verified",
            "enabled": True,
            "last_verified_at": None,
            "last_seen_at": None,
        }

    with (
        patch.object(
            settings.nexus_peer_repository,
            "get_local_peer_settings",
            return_value=_peer_settings(),
        ),
        patch.object(
            settings.nexus_peer_repository,
            "upsert_verified_peer",
            side_effect=fake_upsert,
        ),
    ):
        result = settings.register_verified_peer(
            peer_id="peer-nexus-remote",
            identity_document=_identity_document(identity),
            peer_base_url="http://192.0.2.10:8561",
        )

    assert captured["public_key_algorithm"] == "Ed25519"
    assert captured["public_key"] == identity["publicKey"]
    assert (
        captured["public_key_fingerprint"]
        == identity["fingerprint"]
    )

    assert result["peer"]["machineIdentity"] == identity


def test_durable_peer_rejects_tampered_fingerprint_before_write():
    identity = _machine_identity()
    identity["fingerprint"] = (
        "sha256:" + ("f" * 64)
    )

    with (
        patch.object(
            settings.nexus_peer_repository,
            "get_local_peer_settings",
            return_value=_peer_settings(),
        ),
        patch.object(
            settings.nexus_peer_repository,
            "upsert_verified_peer",
        ) as upsert,
    ):
        with pytest.raises(
            ValueError,
            match="fingerprint",
        ):
            settings.register_verified_peer(
                peer_id="peer-nexus-remote",
                identity_document=_identity_document(identity),
                peer_base_url="http://192.0.2.10:8561",
            )

    upsert.assert_not_called()


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
def test_machine_identity_does_not_enable_dangerous_capabilities(
    capability,
):
    identity = _machine_identity()
    document = _identity_document(identity)
    document["capabilities"][capability] = True

    with patch.object(
        settings.nexus_peer_repository,
        "get_local_peer_settings",
        return_value=_peer_settings(),
    ):
        with pytest.raises(
            ValueError,
            match="capability",
        ):
            settings.register_verified_peer(
                peer_id="peer-nexus-remote",
                identity_document=document,
                peer_base_url="http://192.0.2.10:8561",
            )
