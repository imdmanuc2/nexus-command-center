"""Cross-layer recovery invariants for Nexus pairing completion."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative):
    return (
        ROOT / relative
    ).read_text(
        encoding="utf-8"
    )


def test_receiver_completion_is_signed_and_legacy_consume_http_is_retired():
    server = _read(
        "backend/api/nexus_peer_server.py"
    )

    assert (
        'ENROLLMENT_COMPLETE_PATH = '
        '"/api/nexus/enrollment/complete"'
        in server
    )

    assert (
        "/api/nexus/enrollment/consume"
        not in server
    )

    assert (
        "ENROLLMENT_CONSUME_PATH"
        not in server
    )

    assert (
        "authenticate_enrollment_completion"
        in server
    )

    assert (
        "complete_remote_enrollment"
        in server
    )


def test_receiver_auth_uses_stored_requester_identity():
    auth = _read(
        "backend/services/"
        "nexus_peer_enrollment_auth_service.py"
    )

    function = auth.split(
        "def authenticate_enrollment_completion(",
        1,
    )[1]

    assert "requested_public_key" in function
    assert "requested_public_key_fingerprint" in function
    assert "requested_remote_instance_id" in function
    assert "request_id" in function

    # Completion must not accept replacement machine identity
    # from the completion payload.
    assert (
        'payload.get("publicKey")'
        not in function
    )

    assert (
        'payload.get("publicKeyFingerprint")'
        not in function
    )


def test_atomic_repository_rebinds_auth_identity_under_lock():
    repository = _read(
        "backend/db/repositories/"
        "nexus_peer_enrollment_repository.py"
    )

    assert "FOR UPDATE" in repository
    assert "request_id" in repository
    assert "requested_remote_instance_id" in repository
    assert "hmac.compare_digest" in repository


def test_receiver_retry_has_durable_peer_recovery_contract():
    repository = _read(
        "backend/db/repositories/"
        "nexus_peer_enrollment_repository.py"
    )

    assert '"used"' in repository
    assert "get_peer" in repository or "SELECT" in repository
    assert "public_key_fingerprint" in repository


def test_initiator_reuses_capability_during_recovery():
    initiator = _read(
        "backend/services/"
        "nexus_peer_pairing_completion_service.py"
    )

    assert "load_credential" in initiator
    assert "generate_credential" not in initiator
    assert "complete_remote_enrollment_request" in initiator


def test_initiator_preserves_existing_machine_bound_peer():
    initiator = _read(
        "backend/services/"
        "nexus_peer_pairing_completion_service.py"
    )

    assert "get_peer_by_instances" in initiator
    assert "_machine_identity_matches" in initiator

    existing_branch = initiator.split(
        "if existing_peer is not None:",
        1,
    )[1].split(
        "else:",
        1,
    )[0]

    assert "register_verified_peer" not in existing_branch


def test_connected_transition_precedes_capability_deletion():
    initiator = _read(
        "backend/services/"
        "nexus_peer_pairing_completion_service.py"
    )

    connected = initiator.rfind(
        'new_status=\n                "connected"'
    )

    deleted = initiator.rfind(
        ".delete_credential("
    )

    assert connected >= 0
    assert deleted > connected


def test_recoverable_completion_path_does_not_transition_failed():
    initiator = _read(
        "backend/services/"
        "nexus_peer_pairing_completion_service.py"
    )

    assert 'new_status="failed"' not in initiator

    assert (
        'new_status=\n                "failed"'
        not in initiator
    )


def test_new_reciprocal_peer_defaults_are_non_authoritative():
    initiator = _read(
        "backend/services/"
        "nexus_peer_pairing_completion_service.py"
    )

    assert '"peerAwareness":\n                True' in initiator
    assert '"federation":\n                False' in initiator
    assert '"cmdbExchange":\n                False' in initiator
    assert '"discoveryExchange":\n                False' in initiator
    assert '"management":\n                False' in initiator
    assert '"authorityDelegation":\n                False' in initiator


def test_completion_protocol_has_no_user_visible_permanent_token():
    files = [
        _read(
            "backend/services/"
            "nexus_peer_pairing_completion_service.py"
        ),
        _read(
            "backend/services/"
            "nexus_peer_enrollment_service.py"
        ),
        _read(
            "backend/services/"
            "nexus_peer_enrollment_client_service.py"
        ),
    ]

    joined = "\n".join(files).lower()

    assert "bearer_token" not in joined
    assert "permanent_token" not in joined
