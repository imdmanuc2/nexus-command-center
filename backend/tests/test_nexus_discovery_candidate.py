import json

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


def test_same_instance_with_different_machine_identity_is_conflict():
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

    try:
        service.merge_candidates([
            first,
            second,
        ])
    except ValueError as exc:
        assert str(exc) == (
            "Conflicting Nexus machine identity for "
            "instanceId nexus-test1234"
        )
    else:
        raise AssertionError(
            "Expected Nexus machine identity conflict"
        )


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



class _FakeResponse:
    def __init__(self, document):
        self.body = json.dumps(document).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.body[:size]


def test_discovery_url_supports_ipv4():
    assert service.discovery_url(
        "192.0.2.10",
        port=8561,
    ) == (
        "http://192.0.2.10:8561"
        "/api/nexus/discovery"
    )


def test_discovery_url_brackets_ipv6():
    assert service.discovery_url(
        "2001:db8::10",
        port=8561,
    ) == (
        "http://[2001:db8::10]:8561"
        "/api/nexus/discovery"
    )


def test_discovery_url_encodes_ipv6_scope():
    assert service.discovery_url(
        "fe80::10%eth0",
        port=8561,
    ) == (
        "http://[fe80::10%25eth0]:8561"
        "/api/nexus/discovery"
    )


def test_locator_falls_back_to_reachable_address():
    requested = []

    def opener(request, timeout):
        requested.append(
            request.full_url
        )

        if "192.0.2.10" in request.full_url:
            raise OSError(
                "unreachable interface"
            )

        return _FakeResponse(
            VALID_DOCUMENT
        )

    candidate = service.candidate_from_locator(
        {
            "source": "nexus-mdns",
            "serviceName": "Test Nexus",
            "port": 8561,
            "addresses": [
                "192.0.2.10",
                "198.51.100.20",
            ],
        },
        opener=opener,
    )

    assert candidate is not None

    assert requested == [
        (
            "http://192.0.2.10:8561"
            "/api/nexus/discovery"
        ),
        (
            "http://198.51.100.20:8561"
            "/api/nexus/discovery"
        ),
    ]

    assert candidate["instanceId"] == (
        "nexus-test1234"
    )

    assert candidate["transport"]["addresses"] == [
        "192.0.2.10",
        "198.51.100.20",
    ]


def test_invalid_identity_document_is_not_candidate():
    def opener(request, timeout):
        invalid = {
            **VALID_DOCUMENT,
            "machineIdentity": {
                **VALID_DOCUMENT[
                    "machineIdentity"
                ],
                "fingerprint": (
                    "sha256:"
                    + ("1" * 64)
                ),
            },
        }

        return _FakeResponse(invalid)

    candidate = service.candidate_from_locator(
        {
            "source": "nexus-mdns",
            "serviceName": "Test Nexus",
            "port": 8561,
            "addresses": [
                "192.0.2.10",
            ],
        },
        opener=opener,
    )

    assert candidate is None


def test_locator_resolution_dedupes_by_stable_identity():
    documents = {
        "192.0.2.10": VALID_DOCUMENT,
        "198.51.100.20": VALID_DOCUMENT,
    }

    def opener(request, timeout):
        for address, document in documents.items():
            if address in request.full_url:
                return _FakeResponse(document)

        raise OSError("unknown address")

    candidates = service.candidates_from_locators(
        [
            {
                "source": "nexus-mdns",
                "serviceName": "Test Nexus A",
                "port": 8561,
                "addresses": [
                    "192.0.2.10",
                ],
            },
            {
                "source": "nexus-mdns",
                "serviceName": "Test Nexus B",
                "port": 8561,
                "addresses": [
                    "198.51.100.20",
                ],
            },
        ],
        opener=opener,
    )

    assert len(candidates) == 1

    assert candidates[0]["transport"]["addresses"] == [
        "192.0.2.10",
        "198.51.100.20",
    ]


def test_unreachable_locator_does_not_create_candidate():
    def opener(request, timeout):
        raise OSError("unreachable")

    candidates = service.candidates_from_locators(
        [
            {
                "source": "nexus-mdns",
                "serviceName": "Offline Nexus",
                "port": 8561,
                "addresses": [
                    "192.0.2.99",
                ],
            },
        ],
        opener=opener,
    )

    assert candidates == []



def test_malformed_locator_port_is_ignored():
    def opener(request, timeout):
        raise AssertionError(
            "network must not be attempted"
        )

    candidate = service.candidate_from_locator(
        {
            "source": "nexus-mdns",
            "serviceName": "Malformed Nexus",
            "port": "not-a-port",
            "addresses": [
                "192.0.2.10",
            ],
        },
        opener=opener,
    )

    assert candidate is None


def test_out_of_range_locator_port_is_ignored():
    def opener(request, timeout):
        raise AssertionError(
            "network must not be attempted"
        )

    candidate = service.candidate_from_locator(
        {
            "source": "nexus-mdns",
            "serviceName": "Malformed Nexus",
            "port": 70000,
            "addresses": [
                "192.0.2.10",
            ],
        },
        opener=opener,
    )

    assert candidate is None
