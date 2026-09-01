"""Normalize mDNS/DNS-SD observations for Nexus discovery.

This module defines the transport boundary only. It does not grant trust,
create peers, write CMDB state, perform enrollment, or open network sockets.
"""

from __future__ import annotations

from typing import Any


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
