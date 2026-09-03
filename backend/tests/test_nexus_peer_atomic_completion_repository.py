"""Isolated tests for identity-bound atomic Nexus completion."""

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from unittest.mock import patch

import pytest

from backend.db.repositories import (
    nexus_peer_enrollment_repository
    as repository,
)


PAIRING_ID = "pairing-test"
REMOTE_ID = "nexus-remote"
HASH = "a" * 64


class FakeCursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.executions = []

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        tb,
    ):
        return False

    def execute(
        self,
        sql,
        params=None,
    ):
        self.executions.append(
            (sql, params)
        )

    def fetchone(self):
        if not self.rows:
            return None

        return self.rows.pop(0)


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


class FakeTransaction:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(
        self,
        exc_type,
        exc,
        tb,
    ):
        return False


def _enrollment(
    *,
    status="approved",
    **changes,
):
    now = datetime.now(
        timezone.utc
    )

    row = {
        "enrollment_id":
            "enroll-test",
        "local_instance_id":
            "nexus-local",
        "request_id":
            PAIRING_ID,
        "secret_hash":
            HASH,
        "status":
            status,
        "requested_remote_instance_id":
            REMOTE_ID,
        "requested_remote_name":
            "Remote Nexus",
        "requested_remote_hostname":
            "remote-host",
        "requested_peer_base_url":
            "http://192.0.2.10:8561",
        "requested_public_key_algorithm":
            "Ed25519",
        "requested_public_key":
            "public-key",
        "requested_public_key_fingerprint":
            "sha256:fingerprint",
        "expires_at":
            now + timedelta(minutes=5),
        "approved_at":
            now
            if status in {
                "approved",
                "used",
            }
            else None,
        "rejected_at":
            None,
        "used_at":
            now
            if status == "used"
            else None,
        "created_at":
            now,
        "updated_at":
            now,
    }

    row.update(changes)
    return row


def _peer(**changes):
    row = {
        "peer_id":
            "peer-nexus-remote",
        "local_instance_id":
            "nexus-local",
        "remote_instance_id":
            REMOTE_ID,
        "organization_id":
            "",
        "site_id":
            "",
        "name":
            "Remote Nexus",
        "hostname":
            "remote-host",
        "peer_base_url":
            "http://192.0.2.10:8561",
        "protocol_name":
            "seymour-nexus-peer",
        "protocol_version":
            "1",
        "public_key_algorithm":
            "Ed25519",
        "public_key":
            "public-key",
        "public_key_fingerprint":
            "sha256:fingerprint",
        "status":
            "verified",
        "enabled":
            True,
        "peer_awareness":
            True,
        "federation_enabled":
            False,
        "cmdb_exchange_enabled":
            False,
        "discovery_exchange_enabled":
            False,
        "management_enabled":
            False,
        "authority_delegation_enabled":
            False,
        "metadata":
            {},
    }

    row.update(changes)
    return row


def _run(
    rows,
    *,
    pairing_id=PAIRING_ID,
    remote_id=REMOTE_ID,
    supplied_hash=HASH,
):
    cursor = FakeCursor(rows)
    connection = FakeConnection(
        cursor
    )

    with patch.object(
        repository,
        "transaction",
        return_value=FakeTransaction(
            connection
        ),
    ):
        result = (
            repository
            .complete_enrollment_atomic(
                enrollment_id=
                    "enroll-test",
                pairing_id=
                    pairing_id,
                authenticated_remote_instance_id=
                    remote_id,
                supplied_secret_hash=
                    supplied_hash,
            )
        )

    return result, cursor


def _sql(cursor):
    return "\n".join(
        statement
        for statement, _
        in cursor.executions
    )


def test_approved_completion_creates_safe_peer():
    approved = _enrollment()
    used = {
        **approved,
        "status": "used",
        "used_at":
            datetime.now(
                timezone.utc
            ),
    }

    result, cursor = _run(
        [
            approved,
            None,
            used,
            _peer(),
        ]
    )

    assert result["created"] is True
    assert (
        result["enrollment"]["status"]
        == "used"
    )

    sql = _sql(cursor)

    assert "FOR UPDATE" in sql
    assert (
        "approved_at IS NOT NULL"
        in sql
    )
    assert (
        "expires_at > NOW()"
        not in sql
    )
    assert (
        "DO NOTHING"
        in sql
    )
    assert (
        "DO UPDATE SET"
        not in sql
    )
    assert (
        "federation_enabled"
        in sql
    )
    assert (
        "management_enabled"
        in sql
    )


def test_pairing_id_mismatch_fails_before_write():
    cursor = FakeCursor(
        [_enrollment()]
    )
    connection = FakeConnection(
        cursor
    )

    with patch.object(
        repository,
        "transaction",
        return_value=FakeTransaction(
            connection
        ),
    ):
        with pytest.raises(
            PermissionError,
            match="pairing identity mismatch",
        ):
            repository.complete_enrollment_atomic(
                enrollment_id=
                    "enroll-test",
                pairing_id=
                    "pairing-other",
                authenticated_remote_instance_id=
                    REMOTE_ID,
                supplied_secret_hash=
                    HASH,
            )

    assert len(
        cursor.executions
    ) == 1


def test_legacy_null_pairing_id_fails_closed():
    with pytest.raises(
        PermissionError,
        match="pairing identity mismatch",
    ):
        _run(
            [
                _enrollment(
                    request_id=None
                )
            ]
        )


def test_authenticated_remote_mismatch_fails_before_write():
    with pytest.raises(
        PermissionError,
        match="authenticated remote identity mismatch",
    ):
        _run(
            [_enrollment()],
            remote_id="nexus-attacker",
        )


def test_wrong_capability_fails_before_write():
    with pytest.raises(
        PermissionError,
        match="authentication failed",
    ):
        _run(
            [_enrollment()],
            supplied_hash="b" * 64,
        )


def test_hash_must_be_lowercase_hex():
    for value in (
        "A" * 64,
        "z" * 64,
        "bad",
    ):
        with pytest.raises(
            ValueError,
            match="lowercase SHA-256",
        ):
            repository.complete_enrollment_atomic(
                enrollment_id=
                    "enroll-test",
                pairing_id=
                    PAIRING_ID,
                authenticated_remote_instance_id=
                    REMOTE_ID,
                supplied_secret_hash=
                    value,
            )


def test_approved_requires_approval_proof():
    with pytest.raises(
        PermissionError,
        match="not approved",
    ):
        _run(
            [
                _enrollment(
                    approved_at=None
                )
            ]
        )


def test_approved_completion_survives_request_expiry():
    approved = _enrollment()

    approved["expires_at"] = (
        datetime.now(timezone.utc)
        - timedelta(minutes=5)
    )

    used = {
        **approved,
        "status": "used",
        "used_at":
            datetime.now(
                timezone.utc
            ),
    }

    created_peer = _peer()

    result, cursor = _run(
        [
            approved,
            None,
            used,
            created_peer,
        ]
    )

    assert result["created"] is True
    assert result["peer"] == created_peer
    assert result["enrollment"]["status"] == "used"

    sql = _sql(cursor)

    assert (
        "INSERT INTO nexus.nexus_peers"
        in sql
    )

    assert (
        "AND expires_at > NOW()"
        not in sql
    )


def test_existing_exact_peer_is_preserved():
    approved = _enrollment()

    existing = _peer(
        name="User Renamed Peer",
        peer_base_url=
            "http://new-address:8561",
        enabled=False,
        peer_awareness=False,
        management_enabled=True,
    )

    used = {
        **approved,
        "status": "used",
        "used_at":
            datetime.now(
                timezone.utc
            ),
    }

    result, cursor = _run(
        [
            approved,
            existing,
            used,
        ]
    )

    assert result["created"] is False
    assert (
        result["peer"]
        == existing
    )

    sql = _sql(cursor)

    assert (
        "INSERT INTO nexus.nexus_peers"
        not in sql
    )


def test_existing_machine_identity_conflict_fails_closed():
    with pytest.raises(
        PermissionError,
        match="Existing peer identity conflicts",
    ):
        _run(
            [
                _enrollment(),
                _peer(
                    public_key=
                        "attacker-key"
                ),
            ]
        )


def test_used_retry_allows_mutable_peer_state():
    peer = _peer(
        name="Changed Name",
        hostname="changed-host",
        peer_base_url=
            "http://changed:8561",
        status="offline",
        enabled=False,
        peer_awareness=False,
        federation_enabled=True,
        cmdb_exchange_enabled=True,
        discovery_exchange_enabled=True,
        management_enabled=True,
        authority_delegation_enabled=True,
    )

    result, cursor = _run(
        [
            _enrollment(
                status="used"
            ),
            peer,
        ]
    )

    assert result["created"] is False
    assert result["peer"] == peer
    assert (
        "INSERT INTO nexus.nexus_peers"
        not in _sql(cursor)
    )


def test_used_retry_machine_identity_conflict_fails():
    with pytest.raises(
        PermissionError,
        match="identity conflicts",
    ):
        _run(
            [
                _enrollment(
                    status="used"
                ),
                _peer(
                    public_key_fingerprint=
                        "sha256:other"
                ),
            ]
        )


def test_used_without_peer_fails_closed():
    with pytest.raises(
        PermissionError,
        match="no durable peer",
    ):
        _run(
            [
                _enrollment(
                    status="used"
                ),
                None,
            ]
        )


@pytest.mark.parametrize(
    "status",
    [
        "pending",
        "rejected",
        "expired",
    ],
)
def test_nonapproved_state_fails(status):
    with pytest.raises(
        PermissionError,
        match="not approved",
    ):
        _run(
            [
                _enrollment(
                    status=status
                )
            ]
        )


def test_missing_enrollment_fails_closed():
    with pytest.raises(
        PermissionError,
        match="invalid",
    ):
        _run([None])
