import pytest

from backend.db.repositories import (
    nexus_peer_outbound_pairing_repository as repository,
)


def test_allowed_transition_contract():
    assert repository.ALLOWED_TRANSITIONS == {
        "requesting": {
            "pending",
            "failed",
            "expired",
        },
        "pending": {
            "approved",
            "rejected",
            "failed",
            "expired",
        },
        "approved": {
            "completing",
            "failed",
            "expired",
        },
        "completing": {
            "connected",
            "failed",
            "expired",
        },
    }


@pytest.mark.parametrize(
    ("source", "destination"),
    [
        ("requesting", "approved"),
        ("requesting", "connected"),
        ("pending", "connected"),
        ("pending", "completing"),
        ("approved", "connected"),
        ("completing", "approved"),
        ("connected", "pending"),
        ("rejected", "pending"),
        ("failed", "pending"),
        ("expired", "pending"),
    ],
)
def test_invalid_transition_rejected_before_database(
    monkeypatch,
    source,
    destination,
):
    monkeypatch.setattr(
        repository,
        "get_connection",
        lambda: (_ for _ in ()).throw(
            AssertionError(
                "database must not be touched"
            )
        ),
    )

    with pytest.raises(
        ValueError,
        match="Invalid outbound pairing state transition",
    ):
        repository.transition_pairing(
            pairing_id="pairing-test",
            expected_status=source,
            new_status=destination,
        )


def test_empty_pairing_id_rejected_before_database(
    monkeypatch,
):
    monkeypatch.setattr(
        repository,
        "get_connection",
        lambda: (_ for _ in ()).throw(
            AssertionError(
                "database must not be touched"
            )
        ),
    )

    with pytest.raises(
        ValueError,
        match="pairingId is required",
    ):
        repository.transition_pairing(
            pairing_id="",
            expected_status="requesting",
            new_status="pending",
        )


def test_terminal_states_have_no_outbound_transitions():
    for state in (
        "connected",
        "rejected",
        "failed",
        "expired",
    ):
        assert state not in (
            repository.ALLOWED_TRANSITIONS
        )


def test_happy_path_requires_each_lifecycle_step():
    transitions = (
        ("requesting", "pending"),
        ("pending", "approved"),
        ("approved", "completing"),
        ("completing", "connected"),
    )

    for source, destination in transitions:
        assert (
            destination
            in repository.ALLOWED_TRANSITIONS[source]
        )


def test_rejection_only_from_pending():
    assert (
        "rejected"
        in repository.ALLOWED_TRANSITIONS["pending"]
    )

    for source in (
        "requesting",
        "approved",
        "completing",
    ):
        assert (
            "rejected"
            not in repository.ALLOWED_TRANSITIONS[source]
        )


def test_failure_does_not_allow_reactivation():
    assert (
        "failed"
        in repository.ALLOWED_TRANSITIONS["requesting"]
    )
    assert (
        "failed"
        in repository.ALLOWED_TRANSITIONS["pending"]
    )
    assert (
        "failed"
        in repository.ALLOWED_TRANSITIONS["approved"]
    )
    assert (
        "failed"
        in repository.ALLOWED_TRANSITIONS["completing"]
    )

    assert (
        "failed"
        not in repository.ALLOWED_TRANSITIONS
    )


def test_expiry_does_not_allow_reactivation():
    assert (
        "expired"
        in repository.ALLOWED_TRANSITIONS["requesting"]
    )
    assert (
        "expired"
        in repository.ALLOWED_TRANSITIONS["pending"]
    )
    assert (
        "expired"
        in repository.ALLOWED_TRANSITIONS["approved"]
    )
    assert (
        "expired"
        in repository.ALLOWED_TRANSITIONS["completing"]
    )

    assert (
        "expired"
        not in repository.ALLOWED_TRANSITIONS
    )
