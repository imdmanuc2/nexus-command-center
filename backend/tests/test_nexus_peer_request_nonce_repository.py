from __future__ import annotations

import inspect

import pytest

from backend.db.repositories import (
    nexus_peer_request_nonce_repository as repository,
)


def test_claim_nonce_requires_identity_and_nonce():
    with pytest.raises(
        ValueError,
        match="local_instance_id",
    ):
        repository.claim_nonce(
            local_instance_id="",
            remote_instance_id="remote",
            nonce="a" * 43,
            request_timestamp=_timestamp(),
            expires_at=_expiry(),
        )

    with pytest.raises(
        ValueError,
        match="remote_instance_id",
    ):
        repository.claim_nonce(
            local_instance_id="local",
            remote_instance_id="",
            nonce="a" * 43,
            request_timestamp=_timestamp(),
            expires_at=_expiry(),
        )

    with pytest.raises(
        ValueError,
        match="nonce",
    ):
        repository.claim_nonce(
            local_instance_id="local",
            remote_instance_id="remote",
            nonce="",
            request_timestamp=_timestamp(),
            expires_at=_expiry(),
        )


def test_claim_nonce_rejects_wrong_nonce_length():
    with pytest.raises(
        ValueError,
        match="256-bit",
    ):
        repository.claim_nonce(
            local_instance_id="local",
            remote_instance_id="remote",
            nonce="short",
            request_timestamp=_timestamp(),
            expires_at=_expiry(),
        )


def test_repository_uses_atomic_conflict_claim():
    source = inspect.getsource(
        repository.claim_nonce
    )

    assert "ON CONFLICT" in source
    assert "DO NOTHING" in source
    assert "cursor.rowcount == 1" in source


def test_repository_has_expiry_pruning():
    source = inspect.getsource(
        repository.prune_expired_nonces
    )

    assert "DELETE FROM" in source
    assert "expires_at <= NOW()" in source


def _timestamp():
    from datetime import datetime, timezone

    return datetime(
        2026,
        8,
        29,
        9,
        0,
        0,
        tzinfo=timezone.utc,
    )


def _expiry():
    from datetime import datetime, timezone

    return datetime(
        2026,
        8,
        29,
        9,
        5,
        0,
        tzinfo=timezone.utc,
    )
