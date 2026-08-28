"""Regression tests for durable peers established from enrollment proof."""

from datetime import datetime, timezone

import pytest

from backend.services import nexus_peer_enrollment_service as service


def _row(*, status="used", approved=True, used=True):
    now = datetime.now(timezone.utc)

    return {
        "enrollment_id": "enroll-test",
        "local_instance_id": "nexus-local",
        "secret_hash": "0" * 64,
        "status": status,
        "requested_remote_instance_id": "nexus-remote",
        "requested_remote_name": "Remote Nexus",
        "requested_remote_hostname": "remote-host",
        "requested_peer_base_url": "http://192.0.2.10:8561",
        "expires_at": now,
        "approved_at": now if approved else None,
        "rejected_at": None,
        "used_at": now if used else None,
        "created_at": now,
        "updated_at": now,
    }


def test_consumed_enrollment_registers_safe_peer(monkeypatch):
    row = _row()
    captured = {}

    monkeypatch.setattr(
        service,
        "_require_connections_enabled",
        lambda: {"instance_id": "nexus-local"},
    )

    monkeypatch.setattr(
        service.nexus_peer_enrollment_repository,
        "get_enrollment",
        lambda enrollment_id: row,
    )

    def register_verified_peer(**kwargs):
        captured.update(kwargs)

        document = kwargs["identity_document"]

        return {
            "status": "ok",
            "peer": {
                "peerId": kwargs["peer_id"],
                "remoteInstanceId":
                    document["instance"]["instanceId"],
                "capabilities":
                    document["capabilities"],
            },
        }

    monkeypatch.setattr(
        service.nexus_peer_settings_service,
        "register_verified_peer",
        register_verified_peer,
    )

    result = service.establish_consumed_enrollment_peer(
        enrollment_id="enroll-test"
    )

    assert result["status"] == "ok"
    assert result["established"] is True

    assert captured["peer_id"] == "peer-nexus-remote"

    assert (
        captured["peer_base_url"]
        == "http://192.0.2.10:8561"
    )

    document = captured["identity_document"]

    assert document["instance"]["instanceId"] == "nexus-remote"
    assert document["instance"]["name"] == "Remote Nexus"
    assert document["instance"]["hostname"] == "remote-host"

    assert document["capabilities"] == {
        "peerAwareness": True,
        "federation": False,
        "cmdbExchange": False,
        "discoveryExchange": False,
        "management": False,
        "authorityDelegation": False,
    }

    assert "credential" not in captured
    assert "secret" not in captured


@pytest.mark.parametrize(
    "status,approved,used",
    [
        ("pending", False, False),
        ("approved", True, False),
        ("rejected", False, False),
        ("expired", False, False),
    ],
)
def test_unconsumed_enrollment_cannot_register_peer(
    monkeypatch,
    status,
    approved,
    used,
):
    row = _row(
        status=status,
        approved=approved,
        used=used,
    )

    called = {"register": False}

    monkeypatch.setattr(
        service,
        "_require_connections_enabled",
        lambda: {"instance_id": "nexus-local"},
    )

    monkeypatch.setattr(
        service.nexus_peer_enrollment_repository,
        "get_enrollment",
        lambda enrollment_id: row,
    )

    def register_verified_peer(**kwargs):
        called["register"] = True
        raise AssertionError(
            "peer registration must not occur"
        )

    monkeypatch.setattr(
        service.nexus_peer_settings_service,
        "register_verified_peer",
        register_verified_peer,
    )

    with pytest.raises(PermissionError):
        service.establish_consumed_enrollment_peer(
            enrollment_id="enroll-test"
        )

    assert called["register"] is False


def test_missing_enrollment_cannot_register_peer(monkeypatch):
    called = {"register": False}

    monkeypatch.setattr(
        service,
        "_require_connections_enabled",
        lambda: {"instance_id": "nexus-local"},
    )

    monkeypatch.setattr(
        service.nexus_peer_enrollment_repository,
        "get_enrollment",
        lambda enrollment_id: None,
    )

    def register_verified_peer(**kwargs):
        called["register"] = True

    monkeypatch.setattr(
        service.nexus_peer_settings_service,
        "register_verified_peer",
        register_verified_peer,
    )

    with pytest.raises(PermissionError):
        service.establish_consumed_enrollment_peer(
            enrollment_id="enroll-missing"
        )

    assert called["register"] is False
