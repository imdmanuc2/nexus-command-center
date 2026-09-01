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


class _FakeServiceInfo:
    def __init__(
        self,
        *,
        server="peer.local.",
        port=8561,
        addresses=None,
    ):
        self.server = server
        self.port = port
        self._addresses = list(addresses or [])

    def parsed_addresses(self, version):
        assert version is not None
        return list(self._addresses)


def test_service_info_maps_to_transport_observation():
    info = _FakeServiceInfo(
        server="peer.local.",
        port=8561,
        addresses=[
            "192.0.2.50",
            "fe80::50",
        ],
    )

    result = service.observation_from_service_info(
        service_type=service.SERVICE_TYPE,
        service_name=(
            "Peer Nexus."
            "_seymour-nexus._tcp.local."
        ),
        info=info,
    )

    assert result["server"] == "peer.local"
    assert result["port"] == 8561
    assert result["addresses"] == [
        "192.0.2.50",
        "fe80::50",
    ]


class _FakeZeroconf:
    instances = []

    def __init__(self, *, ip_version):
        self.ip_version = ip_version
        self.closed = False
        self.info = {
            "Peer Nexus._seymour-nexus._tcp.local.": (
                _FakeServiceInfo(
                    addresses=["192.0.2.50"]
                )
            ),
        }
        self.__class__.instances.append(self)

    def get_service_info(
        self,
        service_type,
        name,
    ):
        assert service_type == service.SERVICE_TYPE
        return self.info.get(name)

    def close(self):
        self.closed = True


class _FakeBrowser:
    instances = []

    def __init__(
        self,
        zeroconf,
        service_type,
        *,
        listener,
    ):
        self.cancelled = False
        self.__class__.instances.append(self)

        listener.add_service(
            zeroconf,
            service_type,
            "Peer Nexus._seymour-nexus._tcp.local.",
        )

    def cancel(self):
        self.cancelled = True


def test_browse_collects_without_creating_trust():
    _FakeZeroconf.instances.clear()
    _FakeBrowser.instances.clear()

    sleeps = []

    result = service.browse_service_observations(
        wait_seconds=0.25,
        zeroconf_factory=_FakeZeroconf,
        browser_factory=_FakeBrowser,
        sleep=sleeps.append,
    )

    assert sleeps == [0.25]

    assert len(result) == 1
    assert result[0]["source"] == "nexus-mdns"
    assert result[0]["addresses"] == [
        "192.0.2.50"
    ]

    assert _FakeZeroconf.instances[0].closed is True
    assert _FakeBrowser.instances[0].cancelled is True

    serialized = str(result[0])

    assert "trusted" not in serialized
    assert "federation" not in serialized
    assert "management" not in serialized


def test_browse_merges_duplicate_interface_events():
    class DuplicateBrowser(_FakeBrowser):
        def __init__(
            self,
            zeroconf,
            service_type,
            *,
            listener,
        ):
            self.cancelled = False
            self.__class__.instances.append(self)

            name = (
                "Peer Nexus."
                "_seymour-nexus._tcp.local."
            )

            listener.add_service(
                zeroconf,
                service_type,
                name,
            )

            zeroconf.info[name] = _FakeServiceInfo(
                addresses=[
                    "198.51.100.50",
                    "192.0.2.50",
                ]
            )

            listener.update_service(
                zeroconf,
                service_type,
                name,
            )

    _FakeZeroconf.instances.clear()
    DuplicateBrowser.instances.clear()

    result = service.browse_service_observations(
        wait_seconds=0,
        zeroconf_factory=_FakeZeroconf,
        browser_factory=DuplicateBrowser,
        sleep=lambda _: None,
    )

    assert len(result) == 1
    assert result[0]["addresses"] == [
        "192.0.2.50",
        "198.51.100.50",
    ]


def test_unresolved_service_is_ignored():
    class EmptyZeroconf(_FakeZeroconf):
        def __init__(self, *, ip_version):
            super().__init__(
                ip_version=ip_version
            )
            self.info = {}

    _FakeBrowser.instances.clear()

    result = service.browse_service_observations(
        wait_seconds=0,
        zeroconf_factory=EmptyZeroconf,
        browser_factory=_FakeBrowser,
        sleep=lambda _: None,
    )

    assert result == []


def test_browse_wait_is_bounded():
    for value in (-0.1, 30.1):
        try:
            service.browse_service_observations(
                wait_seconds=value,
                zeroconf_factory=_FakeZeroconf,
                browser_factory=_FakeBrowser,
                sleep=lambda _: None,
            )
        except ValueError as exc:
            assert str(exc) == (
                "Nexus mDNS browse wait must be "
                "between 0 and 30 seconds"
            )
        else:
            raise AssertionError(
                "Expected bounded browse wait rejection"
            )



def test_service_info_prefers_scoped_ipv6_addresses():
    class ScopedInfo(_FakeServiceInfo):
        def parsed_scoped_addresses(self, version):
            assert version is not None
            return [
                "192.0.2.50",
                "fe80::50%eth0",
            ]

    result = service.observation_from_service_info(
        service_type=service.SERVICE_TYPE,
        service_name=(
            "Peer Nexus."
            "_seymour-nexus._tcp.local."
        ),
        info=ScopedInfo(
            addresses=[
                "192.0.2.50",
                "fe80::50",
            ]
        ),
    )

    assert result["addresses"] == [
        "192.0.2.50",
        "fe80::50%eth0",
    ]
