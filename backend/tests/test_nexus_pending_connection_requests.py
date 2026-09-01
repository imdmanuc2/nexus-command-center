"""Regression coverage for pending Nexus connection requests."""

from backend.services import nexus_peer_enrollment_service as service


def _settings(enabled):
    return {
        "instance_id": "nexus-local",
        "allow_peer_connections": enabled,
    }


def _row(enrollment_id):
    return {
        "enrollment_id": enrollment_id,
        "local_instance_id": "nexus-local",
        "status": "pending",
        "requested_remote_instance_id": "nexus-remote",
        "requested_remote_name": "Remote Nexus",
        "requested_remote_hostname": "remote-host",
        "requested_peer_base_url": "http://192.0.2.10:8561",
        "requested_public_key_algorithm": "Ed25519",
        "requested_public_key": "public-key",
        "requested_public_key_fingerprint": "sha256:" + ("1" * 64),
        "expires_at": None,
        "approved_at": None,
        "rejected_at": None,
        "used_at": None,
        "created_at": None,
        "updated_at": None,
    }


def test_pending_requests_are_hidden_when_connections_disabled(
    monkeypatch,
):
    monkeypatch.setattr(
        service.nexus_peer_repository,
        "get_local_peer_settings",
        lambda: _settings(False),
    )

    called = {"list": False}

    def list_rows():
        called["list"] = True
        return []

    monkeypatch.setattr(
        service.nexus_peer_enrollment_repository,
        "list_pending_enrollments",
        list_rows,
    )

    result = service.list_pending_connection_requests()

    assert result == {
        "status": "ok",
        "enabled": False,
        "count": 0,
        "requests": [],
    }

    assert called["list"] is False


def test_pending_requests_are_publicly_serialized_when_enabled(
    monkeypatch,
):
    monkeypatch.setattr(
        service.nexus_peer_repository,
        "get_local_peer_settings",
        lambda: _settings(True),
    )

    monkeypatch.setattr(
        service.nexus_peer_enrollment_repository,
        "list_pending_enrollments",
        lambda: [_row("enroll-test")],
    )

    result = service.list_pending_connection_requests()

    assert result["status"] == "ok"
    assert result["enabled"] is True
    assert result["count"] == 1

    request = result["requests"][0]

    assert request["enrollmentId"] == "enroll-test"
    assert (
        request["requestedRemoteInstanceId"]
        == "nexus-remote"
    )
    assert request["requestedRemoteName"] == "Remote Nexus"

    assert "secretHash" not in request
    assert "secret_hash" not in request
    assert "enrollmentSecret" not in request
