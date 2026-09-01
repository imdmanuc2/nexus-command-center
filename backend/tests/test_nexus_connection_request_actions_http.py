"""HTTP coverage for operator Nexus request approval/rejection."""

import io
import json

from backend.api import server


class FakeHandler:
    def __init__(self, path):
        self.path = path
        self.headers = {
            "Content-Length": "0",
        }
        self.rfile = io.BytesIO(b"")
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
        server.seymour_registration_routes,
        "handle_post",
        lambda handler: False,
    )

    monkeypatch.setattr(
        server.seymour_telemetry_routes,
        "handle_post",
        lambda handler: False,
    )


def test_operator_can_approve_pending_request(
    monkeypatch,
):
    _disable_other_routes(monkeypatch)

    called = {}

    def approve(enrollment_id):
        called["enrollmentId"] = enrollment_id

        return {
            "status": "ok",
            "approved": True,
            "enrollment": {
                "enrollmentId": enrollment_id,
                "status": "approved",
            },
        }

    monkeypatch.setattr(
        server.nexus_peer_enrollment_service,
        "approve_enrollment",
        approve,
    )

    handler = FakeHandler(
        "/api/platform/nexus-connection-requests/"
        "enroll-test/approve"
    )

    server.NexusHandler.do_POST(handler)

    assert called["enrollmentId"] == "enroll-test"
    assert handler.response["status"] == 200
    assert handler.response["payload"]["approved"] is True
    assert (
        handler.response["payload"]["enrollment"]["status"]
        == "approved"
    )


def test_operator_can_reject_pending_request(
    monkeypatch,
):
    _disable_other_routes(monkeypatch)

    called = {}

    def reject(enrollment_id):
        called["enrollmentId"] = enrollment_id

        return {
            "status": "ok",
            "rejected": True,
            "enrollment": {
                "enrollmentId": enrollment_id,
                "status": "rejected",
            },
        }

    monkeypatch.setattr(
        server.nexus_peer_enrollment_service,
        "reject_enrollment",
        reject,
    )

    handler = FakeHandler(
        "/api/platform/nexus-connection-requests/"
        "enroll-test/reject"
    )

    server.NexusHandler.do_POST(handler)

    assert called["enrollmentId"] == "enroll-test"
    assert handler.response["status"] == 200
    assert handler.response["payload"]["rejected"] is True
    assert (
        handler.response["payload"]["enrollment"]["status"]
        == "rejected"
    )


def test_approve_maps_missing_request_to_404(
    monkeypatch,
):
    _disable_other_routes(monkeypatch)

    def missing(enrollment_id):
        raise KeyError("Enrollment not found")

    monkeypatch.setattr(
        server.nexus_peer_enrollment_service,
        "approve_enrollment",
        missing,
    )

    handler = FakeHandler(
        "/api/platform/nexus-connection-requests/"
        "enroll-missing/approve"
    )

    server.NexusHandler.do_POST(handler)

    assert handler.response == {
        "status": 404,
        "payload": {
            "status": "error",
            "error": "not_found",
        },
    }


def test_approve_maps_disabled_or_invalid_state_to_403(
    monkeypatch,
):
    _disable_other_routes(monkeypatch)

    def denied(enrollment_id):
        raise PermissionError(
            "Nexus peer connections are disabled"
        )

    monkeypatch.setattr(
        server.nexus_peer_enrollment_service,
        "approve_enrollment",
        denied,
    )

    handler = FakeHandler(
        "/api/platform/nexus-connection-requests/"
        "enroll-test/approve"
    )

    server.NexusHandler.do_POST(handler)

    assert handler.response["status"] == 403
    assert (
        handler.response["payload"]["error"]
        == "Nexus peer connections are disabled"
    )


def test_action_route_does_not_consume_or_establish_peer(
    monkeypatch,
):
    _disable_other_routes(monkeypatch)

    monkeypatch.setattr(
        server.nexus_peer_enrollment_service,
        "approve_enrollment",
        lambda enrollment_id: {
            "status": "ok",
            "approved": True,
            "enrollment": {
                "enrollmentId": enrollment_id,
                "status": "approved",
            },
        },
    )

    called = {
        "consume": False,
        "establish": False,
    }

    def consume(**kwargs):
        called["consume"] = True
        raise AssertionError(
            "Approval must not consume enrollment"
        )

    def establish(**kwargs):
        called["establish"] = True
        raise AssertionError(
            "Approval must not create peer"
        )

    monkeypatch.setattr(
        server.nexus_peer_enrollment_service,
        "consume_enrollment",
        consume,
    )

    monkeypatch.setattr(
        server.nexus_peer_enrollment_service,
        "establish_consumed_enrollment_peer",
        establish,
    )

    handler = FakeHandler(
        "/api/platform/nexus-connection-requests/"
        "enroll-test/approve"
    )

    server.NexusHandler.do_POST(handler)

    assert handler.response["status"] == 200
    assert called == {
        "consume": False,
        "establish": False,
    }
