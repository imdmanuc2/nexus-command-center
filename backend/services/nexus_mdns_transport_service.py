"""Normalize mDNS/DNS-SD observations for Nexus discovery.

This module defines the transport boundary only. It does not grant trust,
create peers, write CMDB state, perform enrollment, or open network sockets.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable

from zeroconf import (
    IPVersion,
    ServiceBrowser,
    ServiceInfo,
    ServiceListener,
    Zeroconf,
)


SERVICE_TYPE = "_seymour-nexus._tcp.local."
DEFAULT_PORT = 8561
SOURCE = "nexus-mdns"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _addresses(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, str):
        values = [value]
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        values = [value]

    return sorted({
        _text(item)
        for item in values
        if _text(item)
    })


def normalize_service_observation(
    *,
    service_type: str,
    service_name: str,
    server: str = "",
    port: int = DEFAULT_PORT,
    addresses: Any = None,
) -> dict[str, Any]:
    """Normalize one DNS-SD observation into a transport locator."""

    normalized_type = _text(service_type)

    if normalized_type != SERVICE_TYPE:
        raise ValueError(
            "Unsupported Nexus discovery service type"
        )

    normalized_name = _text(service_name)

    if not normalized_name:
        raise ValueError(
            "Nexus discovery service name is required"
        )

    normalized_port = int(port)

    if normalized_port < 1 or normalized_port > 65535:
        raise ValueError(
            "Nexus discovery port is invalid"
        )

    return {
        "source": SOURCE,
        "serviceType": SERVICE_TYPE,
        "serviceName": normalized_name,
        "server": _text(server).rstrip("."),
        "port": normalized_port,
        "addresses": _addresses(addresses),
    }


def locator_key(
    observation: dict[str, Any],
) -> tuple[str, int]:
    """Transport key only; this is not Nexus identity."""

    return (
        _text(observation.get("serviceName")),
        int(observation.get("port") or DEFAULT_PORT),
    )


def merge_service_observations(
    observations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Collapse duplicate interface observations of one DNS-SD service."""

    merged: dict[tuple[str, int], dict[str, Any]] = {}

    for observation in observations:
        key = locator_key(observation)

        if not key[0]:
            raise ValueError(
                "Nexus discovery service name is required"
            )

        existing = merged.get(key)

        if existing is None:
            copy = {
                **observation,
                "addresses": _addresses(
                    observation.get("addresses")
                ),
            }

            merged[key] = copy
            continue

        existing["addresses"] = _addresses(
            list(existing.get("addresses") or [])
            + list(observation.get("addresses") or [])
        )

        if (
            not existing.get("server")
            and observation.get("server")
        ):
            existing["server"] = _text(
                observation["server"]
            ).rstrip(".")

    return sorted(
        merged.values(),
        key=lambda item: (
            item["serviceName"].lower(),
            item["port"],
        ),
    )


def observation_from_service_info(
    *,
    service_type: str,
    service_name: str,
    info: ServiceInfo,
) -> dict[str, Any]:
    """Convert resolved Zeroconf service metadata into a locator."""

    scoped_addresses = getattr(
        info,
        "parsed_scoped_addresses",
        None,
    )

    if callable(scoped_addresses):
        addresses = scoped_addresses(
            IPVersion.All
        )
    else:
        addresses = info.parsed_addresses(
            IPVersion.All
        )

    return normalize_service_observation(
        service_type=service_type,
        service_name=service_name,
        server=info.server or "",
        port=int(info.port),
        addresses=addresses,
    )


class _NexusServiceListener(ServiceListener):
    """Collect resolved Nexus DNS-SD services during one browse window."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._observations: list[dict[str, Any]] = []

    def _resolve(
        self,
        zeroconf: Zeroconf,
        service_type: str,
        name: str,
    ) -> None:
        info = zeroconf.get_service_info(
            service_type,
            name,
        )

        if info is None:
            return

        observation = observation_from_service_info(
            service_type=service_type,
            service_name=name,
            info=info,
        )

        with self._lock:
            self._observations.append(
                observation
            )

    def add_service(
        self,
        zeroconf: Zeroconf,
        service_type: str,
        name: str,
    ) -> None:
        self._resolve(
            zeroconf,
            service_type,
            name,
        )

    def update_service(
        self,
        zeroconf: Zeroconf,
        service_type: str,
        name: str,
    ) -> None:
        self._resolve(
            zeroconf,
            service_type,
            name,
        )

    def remove_service(
        self,
        zeroconf: Zeroconf,
        service_type: str,
        name: str,
    ) -> None:
        return None

    def observations(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    **item,
                    "addresses": list(
                        item.get("addresses") or []
                    ),
                }
                for item in self._observations
            ]


def browse_service_observations(
    *,
    wait_seconds: float = 2.0,
    zeroconf_factory: Callable[..., Zeroconf] = Zeroconf,
    browser_factory: Callable[..., ServiceBrowser] = ServiceBrowser,
    sleep: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    """Browse Nexus mDNS briefly and return normalized transport locators.

    This function performs transport discovery only. Returned observations
    are not trusted Nexus identities and do not create peers or CMDB state.
    """

    wait = float(wait_seconds)

    if wait < 0 or wait > 30:
        raise ValueError(
            "Nexus mDNS browse wait must be between 0 and 30 seconds"
        )

    listener = _NexusServiceListener()

    zeroconf = zeroconf_factory(
        ip_version=IPVersion.All
    )

    browser = None

    try:
        browser = browser_factory(
            zeroconf,
            SERVICE_TYPE,
            listener=listener,
        )

        sleep(wait)

        return merge_service_observations(
            listener.observations()
        )

    finally:
        if browser is not None:
            browser.cancel()

        zeroconf.close()
