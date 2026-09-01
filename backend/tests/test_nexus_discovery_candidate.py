from backend.services import nexus_discovery_candidate_service as service


VALID_DOCUMENT = {
    "status": "ok",
    "service": "nexus-command-center",
    "discoveryVersion": "1",
    "instance": {
        "instanceId": "nexus-test1234",
        "name": "Test Nexus",
        "hostname": "test-host",
    },
    "peerProtocol": {
        "name": "seymour-nexus-peer",
        "version": "1",
    },
    "machineIdentity": {
        "algorithm": "Ed25519",
        "publicKey": (
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
            "AAAAAAAAAAA"
        ),
        "fingerprint": (
            "sha256:66687aadf862bd776c8fc18b"
            "8e9f8e20089714856ee233b3902a591d0d5f2925"
        ),
    },
}


def test_candidate_uses_stable_identity_not_address():
    candidate = service.candidate_from_discovery(
        VALID_DOCUMENT,
        addresses=[
            "192.0.2.10",
            "fe80::10",
        ],
        service_name="Test Nexus",
    )

    assert candidate["instanceId"] == "nexus-test1234"

    assert candidate["machineIdentity"]["fingerprint"].startswith(
        "sha256:"
    )

    assert candidate["transport"]["addresses"] == [
        "192.0.2.10",
        "fe80::10",
    ]

    assert candidate["trusted"] is False


def test_candidate_has_no_privileged_capabilities():
    candidate = service.candidate_from_discovery(
        VALID_DOCUMENT,
        addresses=["192.0.2.10"],
    )

    assert candidate["capabilities"] == {
        "peerAwareness": False,
        "federation": False,
        "cmdbExchange": False,
        "discoveryExchange": False,
        "management": False,
        "authorityDelegation": False,
    }


def test_rejects_invalid_discovery_document():
    invalid = {
        **VALID_DOCUMENT,
        "service": "wrong-service",
    }

    try:
        service.candidate_from_discovery(invalid)
    except ValueError as exc:
        assert str(exc) == "Invalid Nexus discovery document"
    else:
        raise AssertionError("Expected invalid discovery document")


def test_duplicate_interfaces_collapse_to_one_candidate():
    first = service.candidate_from_discovery(
        VALID_DOCUMENT,
        addresses=[
            "192.0.2.10",
            "fe80::10",
        ],
        service_name="Test Nexus",
    )

    second = service.candidate_from_discovery(
        VALID_DOCUMENT,
        addresses=[
            "192.0.2.10",
            "172.20.0.5",
        ],
        service_name="Test Nexus",
    )

    result = service.merge_candidates([
        first,
        second,
    ])

    assert len(result) == 1

    assert result[0]["transport"]["addresses"] == [
        "172.20.0.5",
        "192.0.2.10",
        "fe80::10",
    ]


def test_same_instance_with_different_machine_identity_is_not_merged():
    first = service.candidate_from_discovery(
        VALID_DOCUMENT,
        addresses=["192.0.2.10"],
    )

    second = {
        **first,
        "machineIdentity": {
            **first["machineIdentity"],
            "fingerprint": "sha256:" + ("1" * 64),
        },
    }

    result = service.merge_candidates([
        first,
        second,
    ])

    assert len(result) == 2


def test_observation_is_pending_and_not_trusted():
    candidate = service.candidate_from_discovery(
        VALID_DOCUMENT,
        addresses=[
            "192.0.2.10",
            "fe80::10",
        ],
    )

    observation = service.observation_payload(candidate)

    assert observation["source"] == "nexus-mdns"
    assert observation["status"] == "pending"
    assert observation["confidence"] == 100

    assert (
        observation["metadata"]["nexusInstanceId"]
        == "nexus-test1234"
    )

    assert observation["metadata"]["trusted"] is False

    assert observation["classification"] == {
        "assetType": "nexus-system",
        "primaryRole": "Nexus Command Center",
        "purpose": "Nexus Peer Candidate",
    }


def test_observation_does_not_create_peer_permissions():
    candidate = service.candidate_from_discovery(
        VALID_DOCUMENT,
        addresses=["192.0.2.10"],
    )

    observation = service.observation_payload(candidate)

    serialized = str(observation)

    assert "'federation': True" not in serialized
    assert "'cmdbExchange': True" not in serialized
    assert "'management': True" not in serialized
    assert "'authorityDelegation': True" not in serialized
