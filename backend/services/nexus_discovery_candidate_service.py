"""Normalize and deduplicate automatically discovered Nexus systems.

Discovery candidates are observations only. They grant no trust and do not
create Nexus peers, CMDB assets, federation, management, or authority.
"""

from __future__ import annotations

from typing import Any

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
