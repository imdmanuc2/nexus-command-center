import json

from backend.api import server


class FakeHandler:
    def __init__(self, path):
        self.path = path
        self.response = None

    def _send_json(self, payload, status=200):
        self.response = {
            "status": status,
            "payload": json.loads(
                payload.decode("utf-8")
            ),
        }

        return self.response


def _disable_other_routes(monkeypatch):
    monkeypatch.setattr(
        server.nexus_peer_routes,
        "handle_get",
        lambda handler: False,
    )

    monkeypatch.setattr(
        server.seymour_registration_routes,
        "handle_get",
        lambda handler: False,
    )

    monkeypatch.setattr(
        server.seymour_telemetry_routes,
        "handle_get",
        lambda handler: False,
    )


def test_available_systems_route_returns_service_payload(
    monkeypatch,
):
    _disable_other_routes(monkeypatch)

    expected = {
        "status": "ok",
        "enabled": True,
        "count": 1,
        "candidates": [
            {
                "instanceId": "nexus-remote",
                "trusted": False,
            }
        ],
    }

    monkeypatch.setattr(
        server.nexus_available_systems_service,
        "available_systems",
        lambda: expected,
    )

    handler = FakeHandler(
        "/api/platform/nexus-discovery-candidates"
    )

    server.NexusHandler.do_GET(handler)

    assert handler.response["status"] == 200
    assert handler.response["payload"] == expected


def test_available_systems_route_returns_error_without_side_effect(
    monkeypatch,
):
    _disable_other_routes(monkeypatch)

    def fail():
        raise RuntimeError(
            "Discovery candidate lookup failed"
        )

    monkeypatch.setattr(
        server.nexus_available_systems_service,
        "available_systems",
        fail,
    )

    handler = FakeHandler(
        "/api/platform/nexus-discovery-candidates"
    )

    server.NexusHandler.do_GET(handler)

    assert handler.response["status"] == 503

    assert handler.response["payload"] == {
        "status": "error",
        "error": "Discovery candidate lookup failed",
    }
