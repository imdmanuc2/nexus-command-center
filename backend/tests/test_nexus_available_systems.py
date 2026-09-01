from backend.services import nexus_available_systems_service


def _settings(
    *,
    enabled=True,
    instance_id="nexus-local",
):
    return {
        "status": "ok",
        "settings": {
            "instanceId": instance_id,
            "allowPeerConnections": False,
            "localDiscoveryEnabled": enabled,
        },
    }


def _candidate(
    instance_id="nexus-remote",
):
    return {
        "candidateType": "nexus",
        "status": "discovered",
        "trusted": False,
        "source": "nexus-mdns",
        "instanceId": instance_id,
        "name": "Remote Nexus",
        "hostname": "remote-host",
        "machineIdentity": {
            "algorithm": "Ed25519",
            "publicKey": "public-key",
            "fingerprint": "sha256:" + ("1" * 64),
        },
        "peerProtocol": {
            "name": "seymour-nexus-peer",
            "version": "1",
        },
        "transport": {
            "serviceName": "Remote Nexus._seymour-nexus._tcp.local.",
            "port": 8561,
            "addresses": ["192.0.2.10"],
        },
        "capabilities": {
            "peerAwareness": False,
            "federation": False,
            "cmdbExchange": False,
            "discoveryExchange": False,
            "management": False,
            "authorityDelegation": False,
        },
    }


def test_disabled_returns_empty_without_browsing():
    calls = {
        "peers": 0,
        "browse": 0,
        "resolve": 0,
    }

    def peers_reader():
        calls["peers"] += 1
        return {
            "status": "ok",
            "peers": [],
        }

    def browser(**kwargs):
        calls["browse"] += 1
        return []

    def resolver(*args, **kwargs):
        calls["resolve"] += 1
        return []

    result = (
        nexus_available_systems_service
        .available_systems(
            settings_reader=lambda: _settings(
                enabled=False
            ),
            peers_reader=peers_reader,
            browser=browser,
            resolver=resolver,
        )
    )

    assert result == {
        "status": "ok",
        "enabled": False,
        "count": 0,
        "candidates": [],
    }

    assert calls == {
        "peers": 0,
        "browse": 0,
        "resolve": 0,
    }


def test_enabled_returns_verified_untrusted_candidate():
    candidate = _candidate()

    result = (
        nexus_available_systems_service
        .available_systems(
            settings_reader=lambda: _settings(),
            peers_reader=lambda: {
                "status": "ok",
                "peers": [],
            },
            browser=lambda **kwargs: [
                {
                    "source": "nexus-mdns",
                    "serviceName": "Remote",
                    "port": 8561,
                    "addresses": ["192.0.2.10"],
                }
            ],
            resolver=lambda observations, **kwargs: [
                candidate
            ],
        )
    )

    assert result["status"] == "ok"
    assert result["enabled"] is True
    assert result["count"] == 1

    item = result["candidates"][0]

    assert item["instanceId"] == "nexus-remote"
    assert item["trusted"] is False

    assert item["peerProtocol"] == {
        "name": "seymour-nexus-peer",
        "version": "1",
    }

    assert item["capabilities"] == {
        "peerAwareness": False,
        "federation": False,
        "cmdbExchange": False,
        "discoveryExchange": False,
        "management": False,
        "authorityDelegation": False,
    }


def test_self_candidate_is_filtered():
    result = (
        nexus_available_systems_service
        .available_systems(
            settings_reader=lambda: _settings(),
            peers_reader=lambda: {
                "status": "ok",
                "peers": [],
            },
            browser=lambda **kwargs: [{}],
            resolver=lambda observations, **kwargs: [
                _candidate("nexus-local")
            ],
        )
    )

    assert result["count"] == 0
    assert result["candidates"] == []


def test_connected_peer_is_filtered():
    result = (
        nexus_available_systems_service
        .available_systems(
            settings_reader=lambda: _settings(),
            peers_reader=lambda: {
                "status": "ok",
                "peers": [
                    {
                        "remoteInstanceId":
                            "nexus-remote",
                    }
                ],
            },
            browser=lambda **kwargs: [{}],
            resolver=lambda observations, **kwargs: [
                _candidate("nexus-remote")
            ],
        )
    )

    assert result["count"] == 0
    assert result["candidates"] == []


def test_service_forces_safe_capabilities():
    candidate = _candidate()

    candidate["trusted"] = True

    candidate["capabilities"] = {
        "peerAwareness": True,
        "federation": True,
        "cmdbExchange": True,
        "discoveryExchange": True,
        "management": True,
        "authorityDelegation": True,
    }

    result = (
        nexus_available_systems_service
        .available_systems(
            settings_reader=lambda: _settings(),
            peers_reader=lambda: {
                "status": "ok",
                "peers": [],
            },
            browser=lambda **kwargs: [{}],
            resolver=lambda observations, **kwargs: [
                candidate
            ],
        )
    )

    item = result["candidates"][0]

    assert item["trusted"] is False

    assert not any(
        item["capabilities"].values()
    )


def test_browse_and_fetch_timeouts_are_forwarded():
    captured = {}

    def browser(**kwargs):
        captured["browse"] = kwargs
        return [{"serviceName": "Remote"}]

    def resolver(observations, **kwargs):
        captured["observations"] = observations
        captured["resolver"] = kwargs
        return [_candidate()]

    result = (
        nexus_available_systems_service
        .available_systems(
            browse_seconds=4.5,
            fetch_timeout=17.0,
            settings_reader=lambda: _settings(),
            peers_reader=lambda: {
                "status": "ok",
                "peers": [],
            },
            browser=browser,
            resolver=resolver,
        )
    )

    assert result["count"] == 1

    assert captured["browse"] == {
        "wait_seconds": 4.5,
    }

    assert captured["resolver"] == {
        "timeout": 17.0,
    }
