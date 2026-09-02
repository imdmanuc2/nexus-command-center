"""Tests for narrow authenticated receiver enrollment status."""

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.services import (
    nexus_peer_enrollment_service as service,
)


ENROLLMENT = "enroll-status"
PAIRING = "pairing-status"
REMOTE = "nexus-remote"
LOCAL = "nexus-local"

NOW = datetime.now(timezone.utc)


def _row(
    *,
    status="pending",
    expires_at=None,
):
    return {
        "enrollment_id":
            ENROLLMENT,
        "local_instance_id":
            LOCAL,
        "status":
            status,
        "requested_remote_instance_id":
            REMOTE,
        "request_id":
            PAIRING,
        "expires_at":
            expires_at
            or (
                NOW
                + timedelta(minutes=10)
            ),
    }


@pytest.mark.parametrize(
    "status",
    [
        "pending",
        "approved",
        "rejected",
        "expired",
        "used",
    ],
)
def test_status_returns_only_narrow_lifecycle_projection(
    monkeypatch,
    status,
):
    row = _row(status=status)

    monkeypatch.setattr(
        service.nexus_peer_enrollment_repository,
        "get_enrollment",
        lambda enrollment_id: row,
    )

    result = (
        service.get_remote_enrollment_status(
            enrollment_id=ENROLLMENT,
            pairing_id=PAIRING,
            authenticated_remote_instance_id=REMOTE,
        )
    )

    assert result == {
        "status": "ok",
        "enrollmentId": ENROLLMENT,
        "pairingId": PAIRING,
        "localInstanceId": LOCAL,
        "remoteInstanceId": REMOTE,
        "enrollmentStatus": status,
        "expiresAt": row["expires_at"],
    }

    text = repr(result)

    for forbidden in (
        "publicKey",
        "public_key",
        "capability",
        "Capability",
        "peerBaseUrl",
        "peer_base_url",
        "capabilityHash",
    ):
        assert forbidden not in text


def test_status_rejects_wrong_pairing(monkeypatch):
    row = _row()

    monkeypatch.setattr(
        service.nexus_peer_enrollment_repository,
        "get_enrollment",
        lambda enrollment_id: row,
    )

    with pytest.raises(
        PermissionError,
        match="Enrollment status is invalid",
    ):
        service.get_remote_enrollment_status(
            enrollment_id=ENROLLMENT,
            pairing_id="wrong-pairing",
            authenticated_remote_instance_id=REMOTE,
        )


def test_status_rejects_wrong_authenticated_remote(monkeypatch):
    row = _row()

    monkeypatch.setattr(
        service.nexus_peer_enrollment_repository,
        "get_enrollment",
        lambda enrollment_id: row,
    )

    with pytest.raises(
        PermissionError,
        match="Enrollment status is invalid",
    ):
        service.get_remote_enrollment_status(
            enrollment_id=ENROLLMENT,
            pairing_id=PAIRING,
            authenticated_remote_instance_id="wrong-nexus",
        )


def test_expired_pending_enrollment_is_normalized(monkeypatch):
    row = _row(
        status="pending",
        expires_at=(
            NOW
            - timedelta(minutes=1)
        ),
    )

    expired = {
        **row,
        "status": "expired",
    }

    monkeypatch.setattr(
        service.nexus_peer_enrollment_repository,
        "get_enrollment",
        lambda enrollment_id: row,
    )

    calls = []

    monkeypatch.setattr(
        service.nexus_peer_enrollment_repository,
        "expire_enrollment",
        lambda enrollment_id: (
            calls.append(enrollment_id)
            or expired
        ),
    )

    result = (
        service.get_remote_enrollment_status(
            enrollment_id=ENROLLMENT,
            pairing_id=PAIRING,
            authenticated_remote_instance_id=REMOTE,
        )
    )

    assert calls == [ENROLLMENT]
    assert result["enrollmentStatus"] == "expired"


def test_unknown_internal_status_is_not_exposed(monkeypatch):
    row = _row(
        status="unexpected-state",
    )

    monkeypatch.setattr(
        service.nexus_peer_enrollment_repository,
        "get_enrollment",
        lambda enrollment_id: row,
    )

    with pytest.raises(
        PermissionError,
        match="Enrollment status is invalid",
    ):
        service.get_remote_enrollment_status(
            enrollment_id=ENROLLMENT,
            pairing_id=PAIRING,
            authenticated_remote_instance_id=REMOTE,
        )
