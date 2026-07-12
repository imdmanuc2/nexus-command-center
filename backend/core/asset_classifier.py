"""Canonical Nexus infrastructure asset classification.

All APIs should use this module instead of letting each frontend page guess
whether an object is a pool, ASIC, blockchain node, server, or unknown device.
"""

from __future__ import annotations

from typing import Any, Iterable


CANONICAL_TYPES = {
    "pool",
    "asic",
    "blockchain-node",
    "server",
    "unknown",
}


def _text(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, dict):
        return " ".join(_text(item) for item in value.values())

    if isinstance(value, (list, tuple, set)):
        return " ".join(_text(item) for item in value)

    return str(value)


def _ports(value: Any) -> set[int]:
    result: set[int] = set()

    if value is None:
        return result

    if isinstance(value, dict):
        if "port" in value:
            try:
                result.add(int(value["port"]))
            except (TypeError, ValueError):
                pass

        for nested in value.values():
            result.update(_ports(nested))

        return result

    if isinstance(value, (list, tuple, set)):
        for item in value:
            result.update(_ports(item))

        return result

    try:
        result.add(int(value))
    except (TypeError, ValueError):
        pass

    return result


def normalize_asset_type(value: Any) -> str | None:
    raw = str(value or "").strip().lower().replace("_", "-")

    aliases = {
        "pool": "pool",
        "mining-pool": "pool",
        "solo-pool": "pool",
        "public-pool": "pool",

        "asic": "asic",
        "miner": "asic",
        "asic-miner": "asic",
        "mining-device": "asic",

        "blockchain": "blockchain-node",
        "blockchain-node": "blockchain-node",
        "coin-node": "blockchain-node",
        "bitcoin-node": "blockchain-node",
        "bitcoin-core": "blockchain-node",
        "btc-node": "blockchain-node",
        "bch-node": "blockchain-node",

        "server": "server",
        "host": "server",
        "infrastructure-node": "server",

        "unknown": "unknown",
    }

    return aliases.get(raw)


def classify_asset(
    *,
    object_type: Any = None,
    asset_type: Any = None,
    node_id: Any = None,
    name: Any = None,
    primary_role: Any = None,
    open_ports: Iterable[Any] | Any = None,
    services: Any = None,
    properties: dict[str, Any] | None = None,
) -> str:
    """Return one canonical Nexus asset type."""

    properties = properties or {}

    explicit_candidates = (
        asset_type,
        properties.get("assetType"),
        properties.get("asset_type"),
        properties.get("canonicalType"),
        properties.get("canonical_type"),
        properties.get("deviceType"),
    )

    for candidate in explicit_candidates:
        normalized = normalize_asset_type(candidate)
        if normalized:
            return normalized

    raw_type = str(object_type or "").strip().lower().replace("_", "-")
    object_id = str(node_id or "").strip().lower()

    # Native graph object identity wins over relationship text.
    if raw_type == "pool" or object_id.startswith("pool-"):
        return "pool"

    if raw_type == "asic":
        return "asic"

    if raw_type in {"blockchain-node", "coin-node-rpc"}:
        return "blockchain-node"

    searchable = " ".join(
        [
            _text(name),
            _text(primary_role),
            _text(properties.get("role")),
            _text(properties.get("primaryRole")),
            _text(properties.get("primary_role")),
            _text(properties.get("hostname")),
        ]
    ).lower()

    detected_ports = set()
    detected_ports.update(_ports(open_ports))
    detected_ports.update(_ports(services))
    detected_ports.update(_ports(properties.get("openPorts")))
    detected_ports.update(_ports(properties.get("ports")))
    detected_ports.update(_ports(properties.get("services")))
    detected_ports.update(_ports(properties.get("rpcPort")))
    detected_ports.update(_ports(properties.get("p2pPort")))

    if (
        "blockchain" in searchable
        or "bitcoin core" in searchable
        or "bitcoin node" in searchable
        or "btc node" in searchable
        or "bch node" in searchable
        or 8332 in detected_ports
        or 8333 in detected_ports
    ):
        return "blockchain-node"

    if (
        "asic" in searchable
        or "nano 3" in searchable
        or "mining system" in searchable
        or "miner" in searchable
    ):
        return "asic"

    if (
        "solo pool" in searchable
        or "public pool" in searchable
        or "mining pool" in searchable
        or "mining backend" in searchable
    ):
        return "pool"

    if raw_type in {"host", "server", "infrastructure-node"}:
        return "server"

    return "unknown"


def classify_graph_node(node: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of a graph node with canonical classification fields."""

    result = dict(node)
    properties = dict(result.get("properties") or {})

    canonical_type = classify_asset(
        object_type=result.get("type"),
        asset_type=properties.get("assetType"),
        node_id=result.get("id"),
        name=result.get("label"),
        primary_role=(
            properties.get("primaryRole")
            or properties.get("primary_role")
            or properties.get("role")
        ),
        open_ports=(
            properties.get("openPorts")
            or properties.get("open_ports")
            or properties.get("ports")
        ),
        services=properties.get("services"),
        properties=properties,
    )

    display_types = {
        "pool": "Mining Pool",
        "asic": "ASIC Miner",
        "blockchain-node": "Blockchain Node",
        "server": "Server",
        "unknown": "Unknown Asset",
    }

    properties["assetType"] = canonical_type
    properties["displayType"] = display_types[canonical_type]

    result["properties"] = properties
    return result


def classify_graph_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Add canonical classification to every node in a graph payload."""

    result = dict(payload)
    result["nodes"] = [
        classify_graph_node(node)
        for node in payload.get("nodes", [])
    ]
    return result
