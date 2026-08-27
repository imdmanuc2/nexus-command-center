"""Regression coverage for Nexus peer enrollment TTL policy."""

from backend.services import nexus_peer_enrollment_service


def test_default_peer_enrollment_ttl_is_fifteen_minutes():
    assert (
        nexus_peer_enrollment_service.DEFAULT_TTL_SECONDS
        == 900
    )


def test_default_peer_enrollment_ttl_is_within_policy_bounds():
    service = nexus_peer_enrollment_service

    assert (
        service.MIN_TTL_SECONDS
        <= service.DEFAULT_TTL_SECONDS
        <= service.MAX_TTL_SECONDS
    )


def test_remote_pairing_default_uses_service_default():
    defaults = (
        nexus_peer_enrollment_service
        .create_remote_pairing_request
        .__kwdefaults__
    )

    assert defaults is not None
    assert (
        defaults["ttl_seconds"]
        == nexus_peer_enrollment_service.DEFAULT_TTL_SECONDS
    )


def test_local_enrollment_default_uses_service_default():
    defaults = (
        nexus_peer_enrollment_service
        .create_enrollment
        .__kwdefaults__
    )

    assert defaults is not None
    assert (
        defaults["ttl_seconds"]
        == nexus_peer_enrollment_service.DEFAULT_TTL_SECONDS
    )
