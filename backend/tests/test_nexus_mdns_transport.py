from backend.services import nexus_mdns_transport_service as service


def test_normalizes_nexus_service_observation():
    result = service.normalize_service_observation(
        service_type="_seymour-nexus._tcp.local.",
        service_name="Lab Nexus._seymour-nexus._tcp.local.",
        server="lab-nexus.local.",
        port=8561,
        addresses=[
            "192.0.2.10",
            "fe80::10",
        ],
    )

    assert result == {
        "source": "nexus-mdns",
        "serviceType": "_seymour-nexus._tcp.local.",
        "serviceName": (
            "Lab Nexus._seymour-nexus._tcp.local."
        ),
        "server": "lab-nexus.local",
        "port": 8561,
        "addresses": [
            "192.0.2.10",
            "fe80::10",
        ],
    }


def test_rejects_unrelated_dns_sd_service():
    try:
        service.normalize_service_observation(
            service_type="_http._tcp.local.",
            service_name="Other Service",
        )
    except ValueError as exc:
        assert str(exc) == (
            "Unsupported Nexus discovery service type"
        )
    else:
        raise AssertionError(
            "Expected unrelated service rejection"
        )


def test_rejects_invalid_port():
    try:
        service.normalize_service_observation(
            service_type=service.SERVICE_TYPE,
            service_name="Test Nexus",
            port=70000,
        )
    except ValueError as exc:
        assert str(exc) == (
            "Nexus discovery port is invalid"
        )
    else:
        raise AssertionError(
            "Expected invalid port rejection"
        )


def test_duplicate_interface_observations_merge_addresses():
    first = service.normalize_service_observation(
        service_type=service.SERVICE_TYPE,
        service_name="Test Nexus",
        server="test.local.",
        addresses=[
            "192.0.2.10",
            "fe80::10",
        ],
    )

    second = service.normalize_service_observation(
        service_type=service.SERVICE_TYPE,
        service_name="Test Nexus",
        server="test.local.",
        addresses=[
            "172.20.0.5",
            "192.0.2.10",
        ],
    )

    result = service.merge_service_observations([
        first,
        second,
    ])

    assert len(result) == 1

    assert result[0]["addresses"] == [
        "172.20.0.5",
        "192.0.2.10",
        "fe80::10",
    ]


def test_transport_key_is_not_ip_identity():
    first = service.normalize_service_observation(
        service_type=service.SERVICE_TYPE,
        service_name="Test Nexus",
        addresses=["192.0.2.10"],
    )

    second = service.normalize_service_observation(
        service_type=service.SERVICE_TYPE,
        service_name="Test Nexus",
        addresses=["198.51.100.20"],
    )

    assert (
        service.locator_key(first)
        == service.locator_key(second)
    )


def test_transport_has_no_trust_or_management_state():
    observation = service.normalize_service_observation(
        service_type=service.SERVICE_TYPE,
        service_name="Test Nexus",
        addresses=["192.0.2.10"],
    )

    serialized = str(observation)

    forbidden = [
        "trusted",
        "federation",
        "cmdbExchange",
        "discoveryExchange",
        "management",
        "authorityDelegation",
        "enrollment",
    ]

    for value in forbidden:
        assert value not in serialized
