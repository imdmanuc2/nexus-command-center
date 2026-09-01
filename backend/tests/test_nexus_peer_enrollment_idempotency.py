from pathlib import Path

from backend.db.repositories import (
    nexus_peer_enrollment_repository as repository,
)


MIGRATION = Path(
    "backend/db/migrations/"
    "048_nexus_peer_enrollment_idempotency.sql"
)


def test_migration_adds_request_id():
    text = MIGRATION.read_text(
        encoding="utf-8"
    )

    assert (
        "ADD COLUMN IF NOT EXISTS request_id TEXT"
        in text
    )


def test_migration_uniqueness_is_identity_scoped():
    text = MIGRATION.read_text(
        encoding="utf-8"
    )

    assert (
        "uq_nexus_peer_enrollments_request_identity"
        in text
    )

    assert "local_instance_id" in text
    assert "requested_remote_instance_id" in text
    assert "request_id" in text


def test_migration_does_not_modify_secret_storage():
    text = MIGRATION.read_text(
        encoding="utf-8"
    )

    lowered = text.lower()

    assert "drop column secret_hash" not in lowered
    assert "alter column secret_hash" not in lowered


def test_create_enrollment_accepts_request_id(
    monkeypatch,
):
    captured = {}

    class Cursor:
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
            statement,
            parameters,
        ):
            captured["statement"] = statement
            captured["parameters"] = parameters

        def fetchone(self):
            return {
                "enrollment_id": "enroll-test",
                "request_id": "pairing-test",
            }

    class Connection:
        def __enter__(self):
            return self

        def __exit__(
            self,
            exc_type,
            exc,
            tb,
        ):
            return False

        def cursor(self):
            return Cursor()

        def commit(self):
            captured["committed"] = True

    monkeypatch.setattr(
        repository,
        "get_connection",
        lambda: Connection(),
    )

    result = repository.create_enrollment(
        enrollment_id="enroll-test",
        local_instance_id="nexus-local",
        secret_hash="a" * 64,
        expires_at="2099-01-01T00:00:00Z",
        requested_remote_instance_id=(
            "nexus-remote"
        ),
        requested_remote_name="Remote Nexus",
        requested_remote_hostname="remote",
        requested_peer_base_url=(
            "http://remote:8561"
        ),
        requested_public_key_algorithm=(
            "Ed25519"
        ),
        requested_public_key="public-key",
        requested_public_key_fingerprint=(
            "sha256:fingerprint"
        ),
        request_id="pairing-test",
    )

    assert result["request_id"] == (
        "pairing-test"
    )

    assert "request_id" in (
        captured["statement"]
    )

    assert "pairing-test" in (
        captured["parameters"]
    )

    assert captured["committed"] is True


def test_request_lookup_is_identity_scoped(
    monkeypatch,
):
    captured = {}

    class Cursor:
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
            statement,
            parameters,
        ):
            captured["statement"] = statement
            captured["parameters"] = parameters

        def fetchone(self):
            return {
                "enrollment_id": "enroll-test",
                "local_instance_id": "nexus-local",
                "requested_remote_instance_id":
                    "nexus-remote",
                "request_id": "pairing-test",
            }

    class Connection:
        def __enter__(self):
            return self

        def __exit__(
            self,
            exc_type,
            exc,
            tb,
        ):
            return False

        def cursor(self):
            return Cursor()

    monkeypatch.setattr(
        repository,
        "get_connection",
        lambda: Connection(),
    )

    result = (
        repository
        .get_enrollment_by_request(
            local_instance_id="nexus-local",
            requested_remote_instance_id=(
                "nexus-remote"
            ),
            request_id="pairing-test",
        )
    )

    assert result["enrollment_id"] == (
        "enroll-test"
    )

    statement = captured[
        "statement"
    ]

    assert "local_instance_id = %s" in statement
    assert (
        "requested_remote_instance_id = %s"
        in statement
    )
    assert "request_id = %s" in statement

    assert captured["parameters"] == (
        "nexus-local",
        "nexus-remote",
        "pairing-test",
    )


def test_request_lookup_requires_all_identity_parts():
    for kwargs in (
        {
            "local_instance_id": "",
            "requested_remote_instance_id":
                "nexus-remote",
            "request_id": "pairing-test",
        },
        {
            "local_instance_id":
                "nexus-local",
            "requested_remote_instance_id":
                "",
            "request_id": "pairing-test",
        },
        {
            "local_instance_id":
                "nexus-local",
            "requested_remote_instance_id":
                "nexus-remote",
            "request_id": "",
        },
    ):
        try:
            (
                repository
                .get_enrollment_by_request(
                    **kwargs
                )
            )
        except ValueError:
            pass
        else:
            raise AssertionError(
                "missing request identity accepted"
            )
