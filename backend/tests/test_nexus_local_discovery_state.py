import json

import pytest

from backend.services import (
    nexus_local_discovery_state_service as state_service,
)


def test_public_state_contains_only_transport_fields(
    monkeypatch,
):
    monkeypatch.setattr(
        state_service,
        "runtime_identity",
        lambda: {
            "instanceId": "nexus-test-123",
            "instanceName": "Test Nexus",
            "hostname": "secret-hostname-not-projected",
            "organizationId": "secret-org",
            "siteId": "secret-site",
        },
    )

    result = state_service.public_state(True)

    assert result == {
        "version": 1,
        "enabled": True,
        "instanceId": "nexus-test-123",
        "name": "Test Nexus",
        "port": 8561,
    }

    forbidden = {
        "hostname",
        "organizationId",
        "siteId",
        "token",
        "privateKey",
        "publicKey",
        "fingerprint",
        "allowPeerConnections",
        "federation",
        "cmdbExchange",
        "discoveryExchange",
        "management",
        "authorityDelegation",
    }

    assert forbidden.isdisjoint(result)


def test_public_state_rejects_non_boolean():
    with pytest.raises(
        ValueError,
        match="localDiscoveryEnabled must be a boolean",
    ):
        state_service.public_state(1)


def test_write_public_state_is_atomic_and_valid_json(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        state_service,
        "runtime_identity",
        lambda: {
            "instanceId": "nexus-test-456",
            "instanceName": "Atomic Nexus",
            "hostname": "ignored",
        },
    )

    destination = (
        tmp_path
        / "runtime"
        / "nexus-local-discovery.json"
    )

    result = state_service.write_public_state(
        True,
        path=destination,
    )

    assert destination.exists()

    parsed = json.loads(
        destination.read_text()
    )

    assert parsed == result
    assert parsed["enabled"] is True

    leftovers = list(
        destination.parent.glob(
            ".nexus-local-discovery.json.*.tmp"
        )
    )

    assert leftovers == []


def test_write_public_state_can_project_disabled(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        state_service,
        "runtime_identity",
        lambda: {
            "instanceId": "nexus-test-789",
            "instanceName": "Disabled Nexus",
            "hostname": "ignored",
        },
    )

    destination = (
        tmp_path
        / "nexus-local-discovery.json"
    )

    state_service.write_public_state(
        False,
        path=destination,
    )

    parsed = json.loads(
        destination.read_text()
    )

    assert parsed == {
        "version": 1,
        "enabled": False,
        "instanceId": "nexus-test-789",
        "name": "Disabled Nexus",
        "port": 8561,
    }
