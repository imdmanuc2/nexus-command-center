from __future__ import annotations

from pathlib import Path

import pytest

from backend.db.repositories import nexus_peer_repository


REPOSITORY_PATH = Path(
    "backend/db/repositories/nexus_peer_repository.py"
)


def test_verified_peer_lookup_exists():
    assert callable(
        nexus_peer_repository.get_peer_by_instances
    )


def test_verified_peer_lookup_rejects_missing_local():
    with pytest.raises(
        ValueError,
        match="local_instance_id",
    ):
        nexus_peer_repository.get_peer_by_instances(
            local_instance_id="",
            remote_instance_id="nexus-remote",
        )


def test_verified_peer_lookup_rejects_missing_remote():
    with pytest.raises(
        ValueError,
        match="remote_instance_id",
    ):
        nexus_peer_repository.get_peer_by_instances(
            local_instance_id="nexus-local",
            remote_instance_id="",
        )


def test_verified_peer_lookup_rejects_self_peer():
    with pytest.raises(
        ValueError,
        match="differ",
    ):
        nexus_peer_repository.get_peer_by_instances(
            local_instance_id="nexus-same",
            remote_instance_id="nexus-same",
        )


def test_verified_peer_lookup_uses_exact_identity_pair():
    source = REPOSITORY_PATH.read_text()

    start = source.index(
        "def get_peer_by_instances("
    )

    block = source[start:]

    assert (
        "WHERE local_instance_id = %s"
        in block
    )

    assert (
        "AND remote_instance_id = %s"
        in block
    )

    assert (
        "public_key_algorithm"
        in block
    )

    assert "public_key," in block

    assert (
        "public_key_fingerprint"
        in block
    )

    assert "status," in block
    assert "enabled," in block


def test_lookup_does_not_change_capability_flags():
    source = REPOSITORY_PATH.read_text()

    start = source.index(
        "def get_peer_by_instances("
    )

    block = source[start:]

    forbidden = (
        "UPDATE nexus.nexus_peers",
        "INSERT INTO nexus.nexus_peers",
        "DELETE FROM nexus.nexus_peers",
    )

    for statement in forbidden:
        assert statement not in block
