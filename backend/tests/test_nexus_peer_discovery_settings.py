from backend.services import nexus_peer_settings_service


def test_settings_serialize_local_discovery_disabled():
    result = nexus_peer_settings_service._serialize_settings(
        {
            "instance_id": "nexus-test",
            "allow_peer_connections": False,
            "local_discovery_enabled": False,
            "created_at": None,
            "updated_at": None,
        }
    )

    assert result["instanceId"] == "nexus-test"
    assert result["allowPeerConnections"] is False
    assert result["localDiscoveryEnabled"] is False


def test_settings_serialize_local_discovery_enabled():
    result = nexus_peer_settings_service._serialize_settings(
        {
            "instance_id": "nexus-test",
            "allow_peer_connections": False,
            "local_discovery_enabled": True,
            "created_at": None,
            "updated_at": None,
        }
    )

    assert result["localDiscoveryEnabled"] is True


def test_empty_settings_default_discovery_off():
    result = nexus_peer_settings_service._serialize_settings(
        None
    )

    assert result["allowPeerConnections"] is False
    assert result["localDiscoveryEnabled"] is False


def test_set_local_discovery_rejects_non_boolean():
    try:
        nexus_peer_settings_service.set_local_discovery_enabled(
            "true"
        )
    except ValueError as exc:
        assert (
            str(exc)
            == "localDiscoveryEnabled must be a boolean"
        )
    else:
        raise AssertionError(
            "Expected ValueError for non-boolean discovery setting"
        )


def test_set_local_discovery_preserves_peer_connection_setting(
    monkeypatch,
):
    captured = {}

    def fake_set_local_discovery_enabled(enabled):
        captured["enabled"] = enabled

        return {
            "instance_id": "nexus-test",
            "allow_peer_connections": True,
            "local_discovery_enabled": enabled,
            "created_at": None,
            "updated_at": None,
        }

    monkeypatch.setattr(
        nexus_peer_settings_service.nexus_peer_repository,
        "set_local_discovery_enabled",
        fake_set_local_discovery_enabled,
    )

    result = (
        nexus_peer_settings_service
        .set_local_discovery_enabled(True)
    )

    assert captured["enabled"] is True

    assert (
        result["settings"]["allowPeerConnections"]
        is True
    )

    assert (
        result["settings"]["localDiscoveryEnabled"]
        is True
    )

    assert result["capabilities"] == {
        "peerAwareness": True,
        "federation": False,
        "cmdbExchange": False,
        "discoveryExchange": False,
        "management": False,
        "authorityDelegation": False,
    }
