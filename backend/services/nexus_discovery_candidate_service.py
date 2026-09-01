"""Normalize and deduplicate automatically discovered Nexus systems.

Discovery candidates are observations only. They grant no trust and do not
create Nexus peers, CMDB assets, federation, management, or authority.
"""

from __future__ import annotations

import ipaddress
import json
from typing import Any, Callable
from urllib.parse import quote
from urllib.request import Request, urlopen

from backend.core import discovery


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


DISCOVERY_PATH = "/api/nexus/discovery"
MAX_DISCOVERY_BYTES = 750000
DEFAULT_FETCH_TIMEOUT = 3.0


def discovery_url(
    address: str,
    *,
    port: int = 8561,
) -> str:
    """Build a safe Nexus discovery URL for IPv4 or IPv6."""

    normalized = _text(address)

    if not normalized:
        raise ValueError(
            "Nexus discovery address is required"
        )

    normalized_port = int(port)

    if normalized_port < 1 or normalized_port > 65535:
        raise ValueError(
            "Nexus discovery port is invalid"
        )

    host = normalized

    try:
        parsed = ipaddress.ip_address(
            normalized.split("%", 1)[0]
        )
    except ValueError:
        raise ValueError(
            "Nexus discovery address must be an IP address"
        ) from None

    if parsed.version == 6:
        if "%" in normalized:
            base, scope = normalized.split("%", 1)

            if not scope:
                raise ValueError(
                    "Nexus IPv6 scope is invalid"
                )

            host = (
                base
                + "%25"
                + quote(scope, safe="")
            )

        host = "[" + host + "]"

    return (
        "http://"
        + host
        + ":"
        + str(normalized_port)
        + DISCOVERY_PATH
    )


def fetch_discovery_document(
    url: str,
    *,
    timeout: float = DEFAULT_FETCH_TIMEOUT,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, Any] | None:
    """Fetch one public Nexus discovery document.

    Failure to reach one transport locator is nonfatal.
    """

    request = Request(
        url,
        headers={
            "User-Agent": "Nexus-Discovery/0.1",
        },
    )

    try:
        with opener(
            request,
            timeout=float(timeout),
        ) as response:
            body = response.read(
                MAX_DISCOVERY_BYTES + 1
            )

            if len(body) > MAX_DISCOVERY_BYTES:
                return None

            document = json.loads(
                body.decode(
                    "utf-8",
                    errors="strict",
                )
            )

    except Exception:
        return None

    if not discovery._valid_nexus_discovery_document(
        document
    ):
        return None

    return document


def candidate_from_locator(
    observation: dict[str, Any],
    *,
    timeout: float = DEFAULT_FETCH_TIMEOUT,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, Any] | None:
    """Resolve one mDNS locator into a verified Nexus candidate."""

    if not isinstance(observation, dict):
        raise ValueError(
            "Nexus discovery observation must be an object"
        )

    addresses = _addresses(
        observation.get("addresses")
    )

    try:
        port = int(
            observation.get("port") or 8561
        )
    except (TypeError, ValueError):
        return None

    if port < 1 or port > 65535:
        return None

    for address in addresses:
        try:
            url = discovery_url(
                address,
                port=port,
            )
        except (TypeError, ValueError):
            continue

        document = fetch_discovery_document(
            url,
            timeout=timeout,
            opener=opener,
        )

        if document is None:
            continue

        return candidate_from_discovery(
            document,
            addresses=addresses,
            port=port,
            service_name=_text(
                observation.get("serviceName")
            ),
            source=_text(
                observation.get("source")
            ) or "nexus-mdns",
        )

    return None


def candidates_from_locators(
    observations: list[dict[str, Any]],
    *,
    timeout: float = DEFAULT_FETCH_TIMEOUT,
    opener: Callable[..., Any] = urlopen,
) -> list[dict[str, Any]]:
    """Resolve transport observations and dedupe by Nexus identity."""

    candidates = []

    for observation in observations:
        candidate = candidate_from_locator(
            observation,
            timeout=timeout,
            opener=opener,
        )

        if candidate is not None:
            candidates.append(candidate)

    return merge_candidates(candidates)



def candidate_from_discovery(
    document: dict[str, Any],
    *,
    addresses: Any = None,
    port: int = 8561,
    service_name: str = "",
    source: str = "nexus-mdns",
) -> dict[str, Any]:
    """Create an untrusted discovery candidate from a verified document."""

    if not discovery._valid_nexus_discovery_document(document):
        raise ValueError("Invalid Nexus discovery document")

    instance = document["instance"]
    machine = document["machineIdentity"]
    protocol = document["peerProtocol"]

    normalized_addresses = _addresses(addresses)

    return {
        "candidateType": "nexus",
        "status": "discovered",
        "trusted": False,
        "source": _text(source) or "nexus-mdns",
        "instanceId": _text(instance["instanceId"]),
        "name": _text(instance.get("name")),
        "hostname": _text(instance.get("hostname")),
        "machineIdentity": {
            "algorithm": "Ed25519",
            "publicKey": _text(machine["publicKey"]),
            "fingerprint": _text(machine["fingerprint"]),
        },
        "peerProtocol": {
            "name": _text(protocol["name"]),
            "version": _text(protocol["version"]),
        },
        "transport": {
            "serviceName": _text(service_name),
            "port": int(port),
            "addresses": normalized_addresses,
        },
        "capabilities": {
            "peerAwareness": False,
            "federation": False,
            "cmdbExchange": False,
            "discoveryExchange": False,
            "management": False,
            "authorityDelegation": False,
        },
    }


def candidate_key(candidate: dict[str, Any]) -> tuple[str, str]:
    """Stable identity key independent of address or network interface."""

    machine = candidate.get("machineIdentity") or {}

    return (
        _text(candidate.get("instanceId")),
        _text(machine.get("fingerprint")),
    )


def merge_candidates(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Collapse repeated transport observations of the same Nexus identity."""

    merged: dict[tuple[str, str], dict[str, Any]] = {}
    fingerprints_by_instance: dict[str, str] = {}

    for candidate in candidates:
        key = candidate_key(candidate)

        if not key[0] or not key[1]:
            raise ValueError(
                "Nexus candidate requires instanceId and fingerprint"
            )

        instance_id, fingerprint = key

        known_fingerprint = fingerprints_by_instance.get(instance_id)

        if (
            known_fingerprint
            and known_fingerprint != fingerprint
        ):
            raise ValueError(
                "Conflicting Nexus machine identity for "
                f"instanceId {instance_id}"
            )

        fingerprints_by_instance[instance_id] = fingerprint

        existing = merged.get(key)

        if existing is None:
            copy = {
                **candidate,
                "machineIdentity": dict(
                    candidate.get("machineIdentity") or {}
                ),
                "peerProtocol": dict(
                    candidate.get("peerProtocol") or {}
                ),
                "transport": dict(
                    candidate.get("transport") or {}
                ),
                "capabilities": dict(
                    candidate.get("capabilities") or {}
                ),
            }

            copy["transport"]["addresses"] = _addresses(
                copy["transport"].get("addresses")
            )

            merged[key] = copy
            continue

        existing_transport = existing["transport"]
        incoming_transport = candidate.get("transport") or {}

        existing_transport["addresses"] = _addresses(
            list(existing_transport.get("addresses") or [])
            + list(incoming_transport.get("addresses") or [])
        )

        if (
            not existing_transport.get("serviceName")
            and incoming_transport.get("serviceName")
        ):
            existing_transport["serviceName"] = _text(
                incoming_transport["serviceName"]
            )

    return sorted(
        merged.values(),
        key=lambda item: (
            item["name"].lower(),
            item["instanceId"],
            item["machineIdentity"]["fingerprint"],
        ),
    )


def observation_payload(
    candidate: dict[str, Any],
) -> dict[str, Any]:
    """Map a Nexus candidate into the existing observation staging contract."""

    machine = candidate.get("machineIdentity") or {}
    transport = candidate.get("transport") or {}

    addresses = _addresses(
        transport.get("addresses")
    )

    primary_ip = addresses[0] if addresses else ""

    return {
        "source": candidate.get("source") or "nexus-mdns",
        "status": "pending",
        "confidence": 100,
        "hostname": candidate.get("hostname") or "",
        "ip": primary_ip,
        "assetType": "nexus-system",
        "primaryRole": "Nexus Command Center",
        "purpose": "Nexus Peer Candidate",
        "openPorts": [int(transport.get("port") or 8561)],
        "services": ["nexus-peer"],
        "capabilities": [],
        "identity": {
            "ip": primary_ip,
            "hostname": candidate.get("hostname") or "",
        },
        "classification": {
            "assetType": "nexus-system",
            "primaryRole": "Nexus Command Center",
            "purpose": "Nexus Peer Candidate",
        },
        "network": {
            "ip": primary_ip,
            "addresses": addresses,
            "openPorts": [
                int(transport.get("port") or 8561)
            ],
        },
        "metadata": {
            "discoverySource": candidate.get("source") or "nexus-mdns",
            "nexusInstanceId": candidate.get("instanceId") or "",
            "machineFingerprint": machine.get("fingerprint") or "",
            "trusted": False,
        },
        "raw": {
            "candidate": candidate,
        },
    }
