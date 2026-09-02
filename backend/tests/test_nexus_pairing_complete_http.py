from __future__ import annotations

import json

from backend.api import server


PAIRING = "pairing-test"


class _Handler:
    def __init__(
        self,
        *,
        body=None,
    ):
        self.path = (
            "/api/platform/"
            "nexus-pairings/"
            f"{PAIRING}/complete"
        )
        self._body = (
            {}
            if body is None
            else body
        )
        self.response = None

    def _read_json_body(self):
        return self._body

    def _send_json(
        self,
        payload,
        status=200,
    ):
        self.response = (
            status,
            json.loads(
                payload.decode("utf-8")
            ),
        )
        return self.response


def _run(
    *,
    body=None,
):
    handler = _Handler(
        body=body,
    )

    server.NexusHandler.do_POST(
        handler
    )

    return handler.response


def test_complete_uses_pairing_id_from_path_only(
    monkeypatch,
):
    captured = {}

    def complete_pairing(
        *,
        pairing_id,
    ):
        captured["pairing_id"] = (
            pairing_id
        )

        return {
            "status": "connected",
            "pairingId": pairing_id,
            "remoteInstanceId":
                "remote-1",
            "remoteEnrollmentId":
                "enrollment-1",
            "peerId":
                "peer-remote-1",
            "created": True,
            "alreadyConnected": False,
            "connectedAt": None,
        }

    monkeypatch.setattr(
        server.nexus_peer_pairing_completion_service,
        "complete_pairing",
        complete_pairing,
    )

    status, payload = _run()

    assert status == 200

    assert captured == {
        "pairing_id": PAIRING,
    }

    assert payload["status"] == "connected"
    assert payload["pairingId"] == PAIRING
    assert payload["created"] is True
    assert (
        payload["alreadyConnected"]
        is False
    )


def test_complete_connected_retry_projection(
    monkeypatch,
):
    monkeypatch.setattr(
        server.nexus_peer_pairing_completion_service,
        "complete_pairing",
        lambda *, pairing_id: {
            "status": "connected",
            "pairingId": pairing_id,
            "remoteInstanceId":
                "remote-1",
            "remoteEnrollmentId":
                "enrollment-1",
            "created": False,
            "alreadyConnected": True,
        },
    )

    status, payload = _run()

    assert status == 200
    assert payload["status"] == "connected"
    assert (
        payload["alreadyConnected"]
        is True
    )


def test_complete_rejects_browser_capability(
    monkeypatch,
):
    called = False

    def complete(**kwargs):
        nonlocal called
        called = True

        raise AssertionError(
            "completion must not run"
        )

    monkeypatch.setattr(
        server.nexus_peer_pairing_completion_service,
        "complete_pairing",
        complete,
    )

    status, payload = _run(
        body={
            "enrollmentCapability":
                "browser-secret",
        }
    )

    assert status == 400
    assert payload["status"] == "error"
    assert called is False


def test_complete_rejects_browser_enrollment_id(
    monkeypatch,
):
    called = False

    def complete(**kwargs):
        nonlocal called
        called = True

        raise AssertionError(
            "completion must not run"
        )

    monkeypatch.setattr(
        server.nexus_peer_pairing_completion_service,
        "complete_pairing",
        complete,
    )

    status, payload = _run(
        body={
            "enrollmentId":
                "browser-enrollment",
        }
    )

    assert status == 400
    assert called is False


def test_complete_rejects_browser_peer_url(
    monkeypatch,
):
    called = False

    def complete(**kwargs):
        nonlocal called
        called = True

        raise AssertionError(
            "completion must not run"
        )

    monkeypatch.setattr(
        server.nexus_peer_pairing_completion_service,
        "complete_pairing",
        complete,
    )

    status, payload = _run(
        body={
            "peerBaseUrl":
                "http://attacker.example:8561",
        }
    )

    assert status == 400
    assert called is False


def test_complete_rejects_browser_remote_identity(
    monkeypatch,
):
    called = False

    def complete(**kwargs):
        nonlocal called
        called = True

        raise AssertionError(
            "completion must not run"
        )

    monkeypatch.setattr(
        server.nexus_peer_pairing_completion_service,
        "complete_pairing",
        complete,
    )

    status, payload = _run(
        body={
            "remoteInstanceId":
                "attacker",
        }
    )

    assert status == 400
    assert called is False


def test_complete_missing_pairing_is_404(
    monkeypatch,
):
    def missing(
        *,
        pairing_id,
    ):
        raise KeyError(
            "Outbound pairing not found"
        )

    monkeypatch.setattr(
        server.nexus_peer_pairing_completion_service,
        "complete_pairing",
        missing,
    )

    status, payload = _run()

    assert status == 404

    assert (
        payload["error"]
        == "pairing_not_found"
    )


def test_complete_wrong_lifecycle_is_conflict(
    monkeypatch,
):
    def wrong_state(
        *,
        pairing_id,
    ):
        raise PermissionError(
            "Outbound pairing is not "
            "approved for completion"
        )

    monkeypatch.setattr(
        server.nexus_peer_pairing_completion_service,
        "complete_pairing",
        wrong_state,
    )

    status, payload = _run()

    assert status == 409

    assert (
        payload["error"]
        == "pairing_not_approved"
    )


def test_complete_identity_conflict_is_conflict(
    monkeypatch,
):
    def conflict(
        *,
        pairing_id,
    ):
        raise PermissionError(
            "Existing reciprocal peer "
            "machine identity conflicts"
        )

    monkeypatch.setattr(
        server.nexus_peer_pairing_completion_service,
        "complete_pairing",
        conflict,
    )

    status, payload = _run()

    assert status == 409

    assert (
        payload["error"]
        == "pairing_not_approved"
    )

    assert (
        "identity"
        not in json.dumps(payload)
    )


def test_complete_runtime_failure_is_secret_free(
    monkeypatch,
):
    def failure(
        *,
        pairing_id,
    ):
        raise RuntimeError(
            "credential secret or remote "
            "protocol detail"
        )

    monkeypatch.setattr(
        server.nexus_peer_pairing_completion_service,
        "complete_pairing",
        failure,
    )

    status, payload = _run()

    assert status == 502

    assert payload == {
        "status": "error",
        "error":
            "pairing_completion_failed",
    }

    rendered = json.dumps(payload)

    assert "credential" not in rendered
    assert "secret" not in rendered
    assert "remote protocol" not in rendered


def test_complete_unexpected_failure_is_secret_free(
    monkeypatch,
):
    def failure(
        *,
        pairing_id,
    ):
        raise Exception(
            "unexpected sensitive detail"
        )

    monkeypatch.setattr(
        server.nexus_peer_pairing_completion_service,
        "complete_pairing",
        failure,
    )

    status, payload = _run()

    assert status == 502

    assert payload == {
        "status": "error",
        "error":
            "pairing_completion_failed",
    }


def test_reconcile_route_still_uses_status_service(
    monkeypatch,
):
    calls = {
        "status": 0,
        "complete": 0,
    }

    def reconcile(
        *,
        pairing_id,
    ):
        calls["status"] += 1

        return {
            "status": "pending",
            "pairingId": pairing_id,
            "remoteInstanceId":
                "remote-1",
            "remoteEnrollmentId":
                "enrollment-1",
            "remoteStatus":
                "pending",
            "changed": False,
        }

    def complete(
        *,
        pairing_id,
    ):
        calls["complete"] += 1

        raise AssertionError(
            "reconcile must not complete"
        )

    monkeypatch.setattr(
        server.nexus_peer_pairing_status_service,
        "reconcile_pairing_status",
        reconcile,
    )

    monkeypatch.setattr(
        server.nexus_peer_pairing_completion_service,
        "complete_pairing",
        complete,
    )

    handler = _Handler()
    handler.path = (
        "/api/platform/"
        "nexus-pairings/"
        f"{PAIRING}/reconcile"
    )

    server.NexusHandler.do_POST(
        handler
    )

    assert handler.response[0] == 200

    assert calls == {
        "status": 1,
        "complete": 0,
    }
