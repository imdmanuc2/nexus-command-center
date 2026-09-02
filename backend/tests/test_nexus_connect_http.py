from __future__ import annotations

import json

from backend.api import server


class _Handler:
    path = "/api/platform/nexus-connect"

    def __init__(self, body):
        self._body = body
        self.response = None

    def _read_json_body(self):
        return self._body

    def _send_json(self, payload, status=200):
        self.response = (
            status,
            json.loads(payload.decode("utf-8")),
        )
        return self.response


def _candidate():
    return {
        "candidateType": "nexus",
        "status": "discovered",
        "trusted": False,
        "source": "nexus-mdns",
        "instanceId": "remote-1",
        "name": "Remote Nexus",
        "hostname": "remote-host",
        "machineIdentity": {
            "algorithm": "Ed25519",
            "publicKey": "remote-public-key",
            "fingerprint": "sha256:remote",
        },
        "peerProtocol": {
            "name": "seymour-nexus-peer",
            "version": "1",
        },
        "transport": {
            "serviceName": "remote._seymour-nexus._tcp.local.",
            "port": 8561,
            "addresses": [
                "192.0.2.20",
            ],
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


def _run(body):
    handler = _Handler(body)

    server.NexusHandler.do_POST(handler)

    return handler.response


def test_connect_accepts_only_instance_id_and_uses_server_candidate(
    monkeypatch,
):
    candidate = _candidate()
    captured = {}

    monkeypatch.setattr(
        server.nexus_available_systems_service,
        "available_systems",
        lambda: {
            "status": "ok",
            "enabled": True,
            "count": 1,
            "candidates": [candidate],
        },
    )

    monkeypatch.setattr(
        server.nexus_peer_endpoint_service,
        "peer_advertise_url",
        lambda: "http://local.example:8561",
    )

    def request_pairing(**kwargs):
        captured.update(kwargs)

        return {
            "status": "ok",
            "created": True,
            "pairing": {
                "pairingId": "pair-1",
                "remoteInstanceId": "remote-1",
                "status": "pending",
            },
        }

    monkeypatch.setattr(
        server.nexus_peer_pairing_request_service,
        "request_pairing",
        request_pairing,
    )

    status, payload = _run(
        {
            "instanceId": "remote-1",
        }
    )

    assert status == 202
    assert payload["status"] == "ok"

    assert captured == {
        "remote_instance_id": "remote-1",
        "remote_name": "Remote Nexus",
        "remote_hostname": "remote-host",
        "peer_base_url":
            "http://192.0.2.20:8561",
        "remote_public_key_algorithm":
            "Ed25519",
        "remote_public_key":
            "remote-public-key",
        "remote_public_key_fingerprint":
            "sha256:remote",
        "local_peer_base_url":
            "http://local.example:8561",
    }


def test_connect_rejects_browser_supplied_transport_or_identity(
    monkeypatch,
):
    called = False

    def available():
        nonlocal called
        called = True
        raise AssertionError(
            "discovery must not run for invalid body"
        )

    monkeypatch.setattr(
        server.nexus_available_systems_service,
        "available_systems",
        available,
    )

    status, payload = _run(
        {
            "instanceId": "remote-1",
            "peerBaseUrl":
                "http://attacker.example:8561",
        }
    )

    assert status == 400
    assert payload["status"] == "error"
    assert called is False


def test_connect_requires_instance_id(
    monkeypatch,
):
    monkeypatch.setattr(
        server.nexus_available_systems_service,
        "available_systems",
        lambda: (_ for _ in ()).throw(
            AssertionError(
                "discovery must not run"
            )
        ),
    )

    status, payload = _run({})

    assert status == 400
    assert payload["status"] == "error"


def test_connect_candidate_must_be_freshly_available(
    monkeypatch,
):
    monkeypatch.setattr(
        server.nexus_available_systems_service,
        "available_systems",
        lambda: {
            "status": "ok",
            "enabled": True,
            "count": 0,
            "candidates": [],
        },
    )

    monkeypatch.setattr(
        server.nexus_peer_pairing_request_service,
        "request_pairing",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError(
                "pairing must not be requested"
            )
        ),
    )

    status, payload = _run(
        {
            "instanceId": "stale-remote",
        }
    )

    assert status == 404
    assert (
        payload["error"]
        == "discovery_candidate_not_found"
    )


def test_connect_requires_local_discovery_enabled(
    monkeypatch,
):
    monkeypatch.setattr(
        server.nexus_available_systems_service,
        "available_systems",
        lambda: {
            "status": "ok",
            "enabled": False,
            "count": 0,
            "candidates": [],
        },
    )

    status, payload = _run(
        {
            "instanceId": "remote-1",
        }
    )

    assert status == 403
    assert "disabled" in payload["error"]


def test_connect_fails_closed_without_advertise_url(
    monkeypatch,
):
    monkeypatch.setattr(
        server.nexus_available_systems_service,
        "available_systems",
        lambda: {
            "status": "ok",
            "enabled": True,
            "count": 1,
            "candidates": [_candidate()],
        },
    )

    monkeypatch.setattr(
        server.nexus_peer_endpoint_service,
        "peer_advertise_url",
        lambda: (_ for _ in ()).throw(
            RuntimeError(
                "NEXUS_PEER_ADVERTISE_URL "
                "is not configured"
            )
        ),
    )

    monkeypatch.setattr(
        server.nexus_peer_pairing_request_service,
        "request_pairing",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError(
                "pairing must not be requested"
            )
        ),
    )

    status, payload = _run(
        {
            "instanceId": "remote-1",
        }
    )

    assert status == 503
    assert "not configured" in payload["error"]


def test_connect_uses_deterministic_server_side_address(
    monkeypatch,
):
    candidate = _candidate()

    candidate["transport"]["addresses"] = [
        "192.0.2.30",
        "192.0.2.20",
        "192.0.2.30",
    ]

    captured = {}

    monkeypatch.setattr(
        server.nexus_available_systems_service,
        "available_systems",
        lambda: {
            "status": "ok",
            "enabled": True,
            "count": 1,
            "candidates": [candidate],
        },
    )

    monkeypatch.setattr(
        server.nexus_peer_endpoint_service,
        "peer_advertise_url",
        lambda: "http://local.example:8561",
    )

    monkeypatch.setattr(
        server.nexus_peer_pairing_request_service,
        "request_pairing",
        lambda **kwargs: (
            captured.update(kwargs)
            or {
                "status": "ok",
                "created": True,
                "pairing": {
                    "pairingId": "pair-1",
                    "remoteInstanceId":
                        "remote-1",
                    "status": "pending",
                },
            }
        ),
    )

    status, _ = _run(
        {
            "instanceId": "remote-1",
        }
    )

    assert status == 202
    assert (
        captured["peer_base_url"]
        == "http://192.0.2.20:8561"
    )


def test_connect_supports_ipv6_discovery_address(
    monkeypatch,
):
    candidate = _candidate()

    candidate["transport"]["addresses"] = [
        "2001:db8::20",
    ]

    captured = {}

    monkeypatch.setattr(
        server.nexus_available_systems_service,
        "available_systems",
        lambda: {
            "status": "ok",
            "enabled": True,
            "count": 1,
            "candidates": [candidate],
        },
    )

    monkeypatch.setattr(
        server.nexus_peer_endpoint_service,
        "peer_advertise_url",
        lambda: "http://local.example:8561",
    )

    monkeypatch.setattr(
        server.nexus_peer_pairing_request_service,
        "request_pairing",
        lambda **kwargs: (
            captured.update(kwargs)
            or {
                "status": "ok",
                "created": True,
                "pairing": {
                    "pairingId": "pair-1",
                    "remoteInstanceId":
                        "remote-1",
                    "status": "pending",
                },
            }
        ),
    )

    status, _ = _run(
        {
            "instanceId": "remote-1",
        }
    )

    assert status == 202
    assert (
        captured["peer_base_url"]
        == "http://[2001:db8::20]:8561"
    )


def test_connect_does_not_reconcile_or_complete_pairing(
    monkeypatch,
):
    candidate = _candidate()

    monkeypatch.setattr(
        server.nexus_available_systems_service,
        "available_systems",
        lambda: {
            "status": "ok",
            "enabled": True,
            "count": 1,
            "candidates": [candidate],
        },
    )

    monkeypatch.setattr(
        server.nexus_peer_endpoint_service,
        "peer_advertise_url",
        lambda: "http://local.example:8561",
    )

    monkeypatch.setattr(
        server.nexus_peer_pairing_request_service,
        "request_pairing",
        lambda **kwargs: {
            "status": "ok",
            "created": True,
            "pairing": {
                "pairingId": "pair-1",
                "remoteInstanceId": "remote-1",
                "status": "pending",
            },
        },
    )

    status, payload = _run(
        {
            "instanceId": "remote-1",
        }
    )

    assert status == 202
    assert payload["pairing"]["status"] == "pending"
