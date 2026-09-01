"""Tests for atomic Nexus enrollment request creation."""

from backend.db.repositories import (
    nexus_peer_enrollment_repository as repository,
)


class FakeCursor:
    def __init__(
        self,
        *,
        insert_row=None,
        winner_row=None,
    ):
        self.insert_row = insert_row
        self.winner_row = winner_row
        self.executions = []
        self._fetches = []

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
        return False

    def execute(self, sql, params):
        normalized = " ".join(sql.split())

        self.executions.append(
            (normalized, params)
        )

        if normalized.startswith("INSERT INTO"):
            self._fetches.append(
                self.insert_row
            )
        elif normalized.startswith("SELECT *"):
            self._fetches.append(
                self.winner_row
            )
        else:
            raise AssertionError(
                "unexpected SQL"
            )

    def fetchone(self):
        if not self._fetches:
            raise AssertionError(
                "fetchone without result"
            )

        return self._fetches.pop(0)


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
        return False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.commits += 1


def _row(
    enrollment_id="enroll-created",
):
    return {
        "enrollment_id": enrollment_id,
        "local_instance_id": "nexus-local",
        "secret_hash": "a" * 64,
        "status": "pending",
        "requested_remote_instance_id":
            "nexus-remote",
        "requested_remote_name":
            "Remote Nexus",
        "requested_remote_hostname":
            "remote",
        "requested_peer_base_url":
            "http://192.0.2.10:8561",
        "requested_public_key_algorithm":
            "Ed25519",
        "requested_public_key":
            "synthetic-public-key",
        "requested_public_key_fingerprint":
            "sha256:" + ("b" * 64),
        "request_id": "pairing-test",
        "expires_at": "expires",
    }


def _call():
    return repository.create_enrollment_idempotent(
        enrollment_id="enroll-created",
        local_instance_id="nexus-local",
        secret_hash="a" * 64,
        expires_at="expires",
        requested_remote_instance_id=
            "nexus-remote",
        requested_remote_name=
            "Remote Nexus",
        requested_remote_hostname=
            "remote",
        requested_peer_base_url=
            "http://192.0.2.10:8561",
        requested_public_key_algorithm=
            "Ed25519",
        requested_public_key=
            "synthetic-public-key",
        requested_public_key_fingerprint=
            "sha256:" + ("b" * 64),
        request_id="pairing-test",
    )


def test_atomic_create_returns_inserted_row(
    monkeypatch,
):
    cursor = FakeCursor(
        insert_row=_row(),
    )
    connection = FakeConnection(cursor)

    monkeypatch.setattr(
        repository,
        "get_connection",
        lambda: connection,
    )

    result = _call()

    assert (
        result["enrollment_id"]
        == "enroll-created"
    )
    assert len(cursor.executions) == 1
    assert cursor.executions[0][
        0
    ].startswith(
        "INSERT INTO"
    )
    assert "ON CONFLICT (" in (
        cursor.executions[0][0]
    )
    assert "DO NOTHING RETURNING *" in (
        cursor.executions[0][0]
    )
    assert connection.commits == 1


def test_atomic_create_returns_conflict_winner(
    monkeypatch,
):
    cursor = FakeCursor(
        insert_row=None,
        winner_row=_row(
            enrollment_id="enroll-winner",
        ),
    )
    connection = FakeConnection(cursor)

    monkeypatch.setattr(
        repository,
        "get_connection",
        lambda: connection,
    )

    result = _call()

    assert (
        result["enrollment_id"]
        == "enroll-winner"
    )
    assert len(cursor.executions) == 2
    assert cursor.executions[0][
        0
    ].startswith(
        "INSERT INTO"
    )
    assert cursor.executions[1][
        0
    ].startswith(
        "SELECT *"
    )
    assert connection.commits == 1


def test_atomic_create_requires_request_identity():
    try:
        repository.create_enrollment_idempotent(
            enrollment_id="enroll-test",
            local_instance_id="nexus-local",
            secret_hash="a" * 64,
            expires_at="expires",
            requested_remote_instance_id="",
            request_id="pairing-test",
        )
    except ValueError as exc:
        assert (
            "requested_remote_instance_id"
            in str(exc)
        )
    else:
        raise AssertionError(
            "missing remote identity accepted"
        )


def test_atomic_create_requires_request_id():
    try:
        repository.create_enrollment_idempotent(
            enrollment_id="enroll-test",
            local_instance_id="nexus-local",
            secret_hash="a" * 64,
            expires_at="expires",
            requested_remote_instance_id=
                "nexus-remote",
            request_id="",
        )
    except ValueError as exc:
        assert "request_id" in str(exc)
    else:
        raise AssertionError(
            "missing request identity accepted"
        )

def test_atomic_create_fails_closed_when_conflict_winner_missing(
    monkeypatch,
):
    cursor = FakeCursor(
        insert_row=None,
        winner_row=None,
    )
    connection = FakeConnection(cursor)

    monkeypatch.setattr(
        repository,
        "get_connection",
        lambda: connection,
    )

    try:
        _call()
    except RuntimeError as exc:
        assert (
            "winner could not be loaded"
            in str(exc)
        )
    else:
        raise AssertionError(
            "missing conflict winner did not fail closed"
        )

    assert len(cursor.executions) == 2
    assert connection.commits == 0
