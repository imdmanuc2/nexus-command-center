"""Nexus canonical infrastructure asset manager.

This module is the single source of truth for managed infrastructure assets.

Discovery results are staging records. They are not persisted here until the
operator explicitly chooses Add to Infrastructure.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.core.asset_classifier import classify_asset


ASSETS_DB = Path("backend/data/assets.json")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_ports(value: Any) -> list[int]:
    ports: set[int] = set()

    def visit(item: Any) -> None:
        if item is None:
            return

        if isinstance(item, dict):
            if "port" in item:
                try:
                    ports.add(int(item["port"]))
                except (TypeError, ValueError):
                    pass

            for nested in item.values():
                visit(nested)
            return

        if isinstance(item, (list, tuple, set)):
            for nested in item:
                visit(nested)
            return

        try:
            ports.add(int(item))
        except (TypeError, ValueError):
            pass

    visit(value)
    return sorted(ports)


def _normalize_services(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    services: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()

    for item in value:
        if isinstance(item, dict):
            name = (
                item.get("name")
                or item.get("service")
                or item.get("label")
                or "Unknown Service"
            )

            try:
                port = int(item.get("port") or 0)
            except (TypeError, ValueError):
                port = 0

            service = {
                **item,
                "name": str(name),
                "port": port,
            }
        else:
            service = {
                "name": str(item),
                "port": 0,
            }

        key = (service["name"].lower(), service["port"])

        if key not in seen:
            seen.add(key)
            services.append(service)

    return services


def _display_name(asset: dict[str, Any], ip: str) -> str:
    candidates = [
        asset.get("friendlyName"),
        asset.get("displayName"),
        asset.get("name"),
        asset.get("primaryRole"),
        asset.get("hostname"),
        ip,
    ]

    for candidate in candidates:
        value = _string(candidate)
        if value:
            return value

    return ip


def _asset_quality(asset: dict[str, Any]) -> int:
    """Higher score means a record is more authoritative."""

    score = 0

    name = _display_name(asset, _string(asset.get("ip"))).lower()
    asset_type = _string(
        asset.get("assetType")
        or asset.get("canonicalType")
        or asset.get("type")
    ).lower()

    if asset.get("managed") is True:
        score += 100

    if asset.get("lifecycleStatus") == "managed":
        score += 80

    if asset.get("createdAutomatically") is False:
        score += 50

    if asset_type not in {"", "unknown", "infrastructure-node", "host"}:
        score += 40

    if name and "unknown" not in name:
        score += 30

    if name in {
        "bitcoin core",
        "bitcoin cash node",
        "nano 3s",
        "mining system 2",
    }:
        score += 20

    if asset.get("friendlyName"):
        score += 10

    return score


def normalize_asset(
    asset: dict[str, Any],
    *,
    default_ip: str | None = None,
) -> dict[str, Any]:
    item = dict(asset or {})

    ip = _string(item.get("ip") or default_ip)

    if not ip:
        raise ValueError("Infrastructure asset requires an IP address.")

    services = _normalize_services(item.get("services"))
    open_ports = _normalize_ports(
        [
            item.get("openPorts"),
            item.get("open_ports"),
            item.get("ports"),
            services,
        ]
    )

    canonical_type = classify_asset(
        object_type=item.get("type"),
        asset_type=(
            item.get("assetType")
            or item.get("canonicalType")
            or item.get("canonical_type")
        ),
        node_id=item.get("id"),
        name=_display_name(item, ip),
        primary_role=(
            item.get("primaryRole")
            or item.get("primary_role")
            or item.get("purpose")
        ),
        open_ports=open_ports,
        services=services,
        properties=item,
    )

    name = _display_name(item, ip)
    created_at = item.get("createdAt") or now_iso()

    normalized = {
        **item,
        "id": item.get("id") or f"asset-{uuid4().hex[:8]}",
        "ip": ip,
        "name": name,
        "friendlyName": name,
        "displayName": item.get("displayName") or name,
        "type": canonical_type,
        "assetType": canonical_type,
        "canonicalType": canonical_type,
        "purpose": item.get("purpose") or _default_purpose(canonical_type),
        "coin": item.get("coin"),
        "primaryRole": item.get("primaryRole") or item.get("primary_role"),
        "openPorts": open_ports,
        "services": services,
        "managed": bool(item.get("managed", not item.get("createdAutomatically", False))),
        "lifecycleStatus": item.get("lifecycleStatus")
        or (
            "managed"
            if bool(item.get("managed", not item.get("createdAutomatically", False)))
            else "discovered"
        ),
        "createdAutomatically": bool(item.get("createdAutomatically", False)),
        "createdAt": created_at,
        "updatedAt": item.get("updatedAt") or now_iso(),
        "favorite": bool(item.get("favorite", False)),
        "notes": item.get("notes") or "",
        "tags": item.get("tags") or [],
        "location": item.get("location") or "",
        "rack": item.get("rack") or "",
        "position": item.get("position") or "",
        "manufacturer": item.get("manufacturer") or "",
        "model": item.get("model") or "",
        "serialNumber": item.get("serialNumber") or "",
        "macAddress": item.get("macAddress") or "",
        "hostname": item.get("hostname") or "",
        "workerId": item.get("workerId") or "",
        "poolId": item.get("poolId") or "",
        "poolHost": item.get("poolHost") or "",
        "poolGroup": item.get("poolGroup") or "",
    }

    return normalized


def _default_purpose(asset_type: str) -> str:
    return {
        "asic": "Mining",
        "pool": "Mining Pool",
        "blockchain-node": "Blockchain",
        "server": "Infrastructure",
        "unknown": "Unknown",
    }.get(asset_type, "Infrastructure")


def _raw_asset_list(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]

    if isinstance(raw, dict):
        if isinstance(raw.get("assets"), list):
            return [
                item
                for item in raw["assets"]
                if isinstance(item, dict)
            ]

        result: list[dict[str, Any]] = []

        for ip, item in raw.items():
            if isinstance(item, dict):
                result.append({
                    **item,
                    "ip": item.get("ip") or ip,
                })

        return result

    return []


def _merge_assets(
    first: dict[str, Any],
    second: dict[str, Any],
) -> dict[str, Any]:
    """Merge duplicate records while preserving the better identity."""

    if _asset_quality(second) > _asset_quality(first):
        preferred = dict(second)
        fallback = first
    else:
        preferred = dict(first)
        fallback = second

    for key, value in fallback.items():
        current = preferred.get(key)

        if current in (None, "", [], {}):
            preferred[key] = value

    preferred["services"] = _normalize_services(
        list(first.get("services") or [])
        + list(second.get("services") or [])
    )

    preferred["openPorts"] = _normalize_ports(
        [
            first.get("openPorts"),
            second.get("openPorts"),
            preferred["services"],
        ]
    )

    preferred["updatedAt"] = now_iso()

    return normalize_asset(
        preferred,
        default_ip=preferred.get("ip"),
    )


def load_assets() -> list[dict[str, Any]]:
    if not ASSETS_DB.exists():
        return []

    try:
        raw = json.loads(ASSETS_DB.read_text() or "[]")
    except (json.JSONDecodeError, OSError):
        return []

    grouped: dict[str, dict[str, Any]] = {}

    for raw_asset in _raw_asset_list(raw):
        try:
            asset = normalize_asset(
                raw_asset,
                default_ip=raw_asset.get("ip"),
            )
        except ValueError:
            continue

        ip = asset["ip"]

        if ip in grouped:
            grouped[ip] = _merge_assets(grouped[ip], asset)
        else:
            grouped[ip] = asset

    return sorted(
        grouped.values(),
        key=lambda item: (
            item.get("assetType") or "unknown",
            item.get("friendlyName") or item.get("ip"),
        ),
    )


def save_assets(assets: list[dict[str, Any]]) -> None:
    ASSETS_DB.parent.mkdir(parents=True, exist_ok=True)

    normalized_by_ip: dict[str, dict[str, Any]] = {}

    for raw_asset in assets:
        try:
            asset = normalize_asset(
                raw_asset,
                default_ip=raw_asset.get("ip"),
            )
        except ValueError:
            continue

        ip = asset["ip"]

        if ip in normalized_by_ip:
            normalized_by_ip[ip] = _merge_assets(
                normalized_by_ip[ip],
                asset,
            )
        else:
            normalized_by_ip[ip] = asset

    payload = sorted(
        normalized_by_ip.values(),
        key=lambda item: (
            item.get("assetType") or "unknown",
            item.get("friendlyName") or item.get("ip"),
        ),
    )

    ASSETS_DB.write_text(
        json.dumps(payload, indent=2) + "\n"
    )


def migrate_assets() -> list[dict[str, Any]]:
    assets = load_assets()
    save_assets(assets)
    return assets


def get_assets_list(
    *,
    managed_only: bool = False,
) -> list[dict[str, Any]]:
    assets = migrate_assets()

    if managed_only:
        return [
            asset
            for asset in assets
            if asset.get("managed") is True
            and asset.get("lifecycleStatus") == "managed"
        ]

    return assets


def get_asset(ip: str) -> dict[str, Any] | None:
    target = _string(ip)

    return next(
        (
            asset
            for asset in get_assets_list()
            if asset.get("ip") == target
        ),
        None,
    )


def discovery_asset(system: dict[str, Any]) -> dict[str, Any]:
    """Return an existing managed asset or an ephemeral staging record.

    New scan results are deliberately not saved here.
    """

    ip = _string(system.get("ip"))

    existing = get_asset(ip)

    if existing:
        return existing

    role = _string(system.get("primaryRole"))

    asset_type = classify_asset(
        object_type=system.get("type"),
        asset_type=system.get("assetType"),
        name=role or ip,
        primary_role=role,
        open_ports=system.get("openPorts"),
        services=system.get("services"),
        properties=system,
    )

    name = role if role and "unknown" not in role.lower() else ip

    return normalize_asset({
        "id": f"discovered-{ip.replace('.', '-')}",
        "ip": ip,
        "name": name,
        "friendlyName": name,
        "type": asset_type,
        "assetType": asset_type,
        "primaryRole": role,
        "openPorts": system.get("openPorts", []),
        "services": system.get("services", []),
        "managed": False,
        "lifecycleStatus": "discovered",
        "createdAutomatically": True,
    })


def upsert_managed_asset(
    system: dict[str, Any],
) -> dict[str, Any]:
    ip = _string(system.get("ip"))

    if not ip:
        raise ValueError("Cannot add system without an IP address.")

    assets = get_assets_list()
    existing = next(
        (asset for asset in assets if asset.get("ip") == ip),
        None,
    )

    now = now_iso()

    incoming = {
        **(existing or {}),
        **system,
        "ip": ip,
        "friendlyName": (
            system.get("friendlyName")
            or system.get("displayName")
            or system.get("name")
            or system.get("primaryRole")
            or existing and existing.get("friendlyName")
            or ip
        ),
        "name": (
            system.get("friendlyName")
            or system.get("displayName")
            or system.get("name")
            or system.get("primaryRole")
            or existing and existing.get("name")
            or ip
        ),
        "type": (
            system.get("assetType")
            or system.get("canonicalType")
            or system.get("type")
            or existing and existing.get("type")
        ),
        "assetType": (
            system.get("assetType")
            or system.get("canonicalType")
            or system.get("type")
            or existing and existing.get("assetType")
        ),
        "managed": True,
        "lifecycleStatus": "managed",
        "createdAutomatically": False,
        "addedAt": (
            existing and existing.get("addedAt")
        ) or system.get("addedAt") or now,
        "createdAt": (
            existing and existing.get("createdAt")
        ) or now,
        "updatedAt": now,
    }

    managed_asset = normalize_asset(incoming)

    next_assets = [
        asset
        for asset in assets
        if asset.get("ip") != ip
    ]

    next_assets.append(managed_asset)
    save_assets(next_assets)

    return managed_asset


def update_asset(
    ip: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    current = get_asset(ip)

    if not current:
        current = {
            "ip": ip,
            "name": ip,
            "friendlyName": ip,
            "managed": True,
            "lifecycleStatus": "managed",
            "createdAutomatically": False,
        }

    return upsert_managed_asset({
        **current,
        **updates,
        "ip": ip,
    })
