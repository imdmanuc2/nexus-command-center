"""HTTP regression coverage for pending Nexus connection requests."""

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


def test_pending_connection_requests_route(
    monkeypatch,
):
    _disable_other_routes(monkeypatch)

    expected = {
        "status": "ok",
        "enabled": True,
        "count": 1,
        "requests": [
            {
                "enrollmentId": "enroll-test",
                "status": "pending",
            }
        ],
    }

    monkeypatch.setattr(
        server.nexus_peer_enrollment_service,
        "list_pending_connection_requests",
        lambda: expected,
    )

    handler = FakeHandler(
        "/api/platform/nexus-connection-requests"
    )

    server.NexusHandler.do_GET(handler)

    assert handler.response["status"] == 200
    assert handler.response["payload"] == expected


def test_pending_connection_requests_route_failure(
    monkeypatch,
):
    _disable_other_routes(monkeypatch)

    def fail():
        raise RuntimeError(
            "Pending request lookup failed"
        )

    monkeypatch.setattr(
        server.nexus_peer_enrollment_service,
        "list_pending_connection_requests",
        fail,
    )

    handler = FakeHandler(
        "/api/platform/nexus-connection-requests"
    )

    server.NexusHandler.do_GET(handler)

    assert handler.response["status"] == 503
    assert handler.response["payload"] == {
        "status": "error",
        "error": "Pending request lookup failed",
    }
