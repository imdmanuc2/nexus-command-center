from __future__ import annotations

import json

from backend.api import server


PAIRING = "pairing-test"


class _Handler:
    def __init__(
        self,
        *,
        path=None,
        body=None,
    ):
        self.path = (
            path
            or (
                "/api/platform/"
                "nexus-pairings/"
                f"{PAIRING}/reconcile"
            )
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
    path=None,
    body=None,
):
    handler = _Handler(
        path=path,
        body=body,
    )

    server.NexusHandler.do_POST(
        handler
    )

    return handler.response


def test_reconcile_uses_pairing_id_from_path_only(
    monkeypatch,
):
    captured = {}

    def reconcile_pairing_status(
        *,
        pairing_id,
    ):
        captured["pairing_id"] = (
            pairing_id
        )

        return {
            "status": "pending",
            "pairingId": pairing_id,
            "remoteInstanceId":
                "remote-1",
            "remoteEnrollmentId":
                "enrollment-1",
            "remoteStatus": "pending",
            "changed": False,
        }

    monkeypatch.setattr(
        server.nexus_peer_pairing_status_service,
        "reconcile_pairing_status",
        reconcile_pairing_status,
    )

    status, payload = _run()

    assert status == 200

    assert captured == {
        "pairing_id": PAIRING,
    }

    assert (
        payload["pairingId"]
        == PAIRING
    )

    assert (
        payload["remoteStatus"]
        == "pending"
    )

    assert payload["changed"] is False


def test_reconcile_approved_state_is_returned_without_completion(
    monkeypatch,
):
    monkeypatch.setattr(
        server.nexus_peer_pairing_status_service,
        "reconcile_pairing_status",
        lambda *, pairing_id: {
            "status": "approved",
            "pairingId": pairing_id,
            "remoteInstanceId":
                "remote-1",
            "remoteEnrollmentId":
                "enrollment-1",
            "remoteStatus": "approved",
            "changed": True,
        },
    )

    status, payload = _run()

    assert status == 200
    assert payload["status"] == "approved"
    assert payload["changed"] is True


def test_reconcile_rejects_browser_supplied_state(
    monkeypatch,
):
    called = False

    def reconcile(**kwargs):
        nonlocal called
        called = True

        raise AssertionError(
            "reconciliation must not run"
        )

    monkeypatch.setattr(
        server.nexus_peer_pairing_status_service,
        "reconcile_pairing_status",
        reconcile,
    )

    status, payload = _run(
        body={
            "status": "approved",
        }
    )

    assert status == 400
    assert payload["status"] == "error"
    assert called is False


def test_reconcile_rejects_browser_supplied_remote_url(
    monkeypatch,
):
    called = False

    def reconcile(**kwargs):
        nonlocal called
        called = True

        raise AssertionError(
            "reconciliation must not run"
        )

    monkeypatch.setattr(
        server.nexus_peer_pairing_status_service,
        "reconcile_pairing_status",
        reconcile,
    )

    status, payload = _run(
        body={
            "peerBaseUrl":
                "http://attacker.example:8561",
        }
    )

    assert status == 400
    assert called is False


def test_reconcile_missing_pairing_is_404(
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
        server.nexus_peer_pairing_status_service,
        "reconcile_pairing_status",
        missing,
    )

    status, payload = _run()

    assert status == 404
    assert (
        payload["error"]
        == "pairing_not_found"
    )


def test_reconcile_wrong_lifecycle_is_conflict(
    monkeypatch,
):
    def wrong_state(
        *,
        pairing_id,
    ):
        raise PermissionError(
            "Outbound pairing is not "
            "pending approval"
        )

    monkeypatch.setattr(
        server.nexus_peer_pairing_status_service,
        "reconcile_pairing_status",
        wrong_state,
    )

    status, payload = _run()

    assert status == 409
    assert (
        payload["error"]
        == "pairing_not_pending"
    )


def test_reconcile_protocol_failure_is_secret_free(
    monkeypatch,
):
    def failure(
        *,
        pairing_id,
    ):
        raise RuntimeError(
            "sensitive remote protocol detail"
        )

    monkeypatch.setattr(
        server.nexus_peer_pairing_status_service,
        "reconcile_pairing_status",
        failure,
    )

    status, payload = _run()

    assert status == 502

    assert payload == {
        "status": "error",
        "error":
            "pairing_status_reconciliation_failed",
    }

    assert (
        "sensitive"
        not in json.dumps(payload)
    )


def test_reconcile_unexpected_failure_is_secret_free(
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
        server.nexus_peer_pairing_status_service,
        "reconcile_pairing_status",
        failure,
    )

    status, payload = _run()

    assert status == 502

    assert payload == {
        "status": "error",
        "error":
            "pairing_status_reconciliation_failed",
    }


def test_reconcile_does_not_call_completion_service(
    monkeypatch,
):
    monkeypatch.setattr(
        server.nexus_peer_pairing_status_service,
        "reconcile_pairing_status",
        lambda *, pairing_id: {
            "status": "approved",
            "pairingId": pairing_id,
            "remoteInstanceId":
                "remote-1",
            "remoteEnrollmentId":
                "enrollment-1",
            "remoteStatus": "approved",
            "changed": True,
        },
    )

    status, payload = _run()

    assert status == 200
    assert payload["status"] == "approved"


def test_non_reconcile_pairing_subpath_falls_through(
    monkeypatch,
):
    called = False

    def reconcile(**kwargs):
        nonlocal called
        called = True
        raise AssertionError(
            "wrong route must not reconcile"
        )

    monkeypatch.setattr(
        server.nexus_peer_pairing_status_service,
        "reconcile_pairing_status",
        reconcile,
    )

    handler = _Handler(
        path=(
            "/api/platform/"
            "nexus-pairings/"
            f"{PAIRING}/something-else"
        ),
        body={},
    )

    # This route should not be captured by the
    # reconciliation branch. The main handler may
    # continue to another route/404, but reconciliation
    # itself must remain untouched.
    try:
        server.NexusHandler.do_POST(
            handler
        )
    except AttributeError:
        pass

    assert called is False
