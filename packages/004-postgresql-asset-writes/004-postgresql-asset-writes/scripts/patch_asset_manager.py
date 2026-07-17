#!/usr/bin/env python3
"""Patch the current Nexus asset manager to use PostgreSQL persistence."""

from __future__ import annotations

import ast
from pathlib import Path

PATH = Path("backend/core/asset_manager.py")


def replace_function(source: str, name: str, replacement: str) -> str:
    tree = ast.parse(source)
    target = next(
        (node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name),
        None,
    )
    if target is None:
        raise SystemExit(f"Could not find top-level function: {name}")

    lines = source.splitlines(keepends=True)
    start = target.lineno - 1
    end = target.end_lineno
    replacement_text = replacement.rstrip() + "\n\n"
    return "".join(lines[:start]) + replacement_text + "".join(lines[end:])


source = PATH.read_text(encoding="utf-8")

import_anchor = "from backend.core.cmdb_audit import append_event\n"
imports = (
    "from backend.core.cmdb_audit import append_event\n"
    "from backend.db.repositories import asset_repository\n"
    "from backend.db.repositories.asset_repository_extensions import find_by_ip\n"
)
if "from backend.db.repositories import asset_repository" not in source:
    if import_anchor not in source:
        raise SystemExit("Could not find cmdb_audit import anchor")
    source = source.replace(import_anchor, imports, 1)

save_assets = '''def save_assets(assets: list[dict[str, Any]]) -> None:
    """Persist normalized assets to PostgreSQL.

    This compatibility function intentionally does not delete database rows
    missing from the supplied list. Deletion must be an explicit CMDB action.
    """
    for asset in assets:
        asset_repository.upsert_asset(normalize_asset(asset))
'''

migrate_assets = '''def migrate_assets() -> list[dict[str, Any]]:
    """Return canonical assets from PostgreSQL.

    The historical function name is retained for connector compatibility.
    No runtime JSON migration or rewrite occurs here.
    """
    return asset_repository.list_assets(limit=5000)
'''

get_assets_list = '''def get_assets_list() -> list[dict[str, Any]]:
    """Return all canonical CMDB assets from PostgreSQL."""
    return asset_repository.list_assets(limit=5000)
'''

upsert = '''def upsert_managed_asset(
    system: dict[str, Any],
) -> dict[str, Any]:
    """Normalize, reconcile, audit, and persist one managed CMDB asset."""
    if not isinstance(system, dict):
        raise ValueError("Managed asset payload must be an object.")

    audit_context = {
        "actor_type": system.get("_actorType", "system"),
        "actor_id": system.get("_actorId", "nexus"),
        "source": system.get("_source", "asset-manager"),
        "reason": system.get("_reason", ""),
        "correlation_id": system.get("_correlationId"),
        "confidence": system.get("_confidence"),
    }

    clean = {
        key: value
        for key, value in system.items()
        if key not in {
            "_actorType", "_actorId", "_source", "_reason",
            "_correlationId", "_confidence",
        }
    }

    incoming = normalize_asset(clean)
    assets = asset_repository.list_assets(limit=5000)
    incoming_identity = asset_identity(incoming)

    existing = next(
        (asset for asset in assets if asset.get("id") == incoming.get("id")),
        None,
    )

    if existing is None:
        existing = next(
            (
                asset
                for asset in assets
                if asset_identity(asset) == incoming_identity
            ),
            None,
        )

    if existing is None and incoming.get("ip"):
        same_ip = find_by_ip(incoming["ip"])
        same_type = [
            asset
            for asset in same_ip
            if asset.get("assetType") == incoming.get("assetType")
        ]
        if same_type:
            existing = max(same_type, key=_asset_quality)

    before = dict(existing) if existing else None
    merged = {
        **(existing or {}),
        **incoming,
        "id": (existing or {}).get("id") or incoming.get("id"),
        "createdAt": (existing or {}).get("createdAt") or incoming.get("createdAt"),
        "updatedAt": now_iso(),
    }

    managed_asset = normalize_asset(merged)
    persisted = asset_repository.upsert_asset(managed_asset)

    append_event(
        action="asset.updated" if existing else "asset.created",
        asset_id=persisted.get("id"),
        asset_type=persisted.get("assetType"),
        asset_name=(
            persisted.get("friendlyName")
            or persisted.get("name")
            or persisted.get("ip")
        ),
        actor_type=audit_context["actor_type"],
        actor_id=audit_context["actor_id"],
        source=audit_context["source"],
        reason=audit_context["reason"],
        correlation_id=audit_context["correlation_id"],
        confidence=audit_context["confidence"],
        before=before,
        after=persisted,
        metadata={
            "ip": persisted.get("ip"),
            "workerId": persisted.get("workerId"),
            "poolId": persisted.get("poolId"),
            "storage": "postgresql",
        },
    )

    return persisted
'''

update = '''def update_asset(
    ip: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    """Update the highest-quality CMDB asset currently using an IP address."""
    matches = find_by_ip(ip)
    if not matches:
        raise KeyError(f"No managed asset found for IP {ip}")

    existing = max(matches, key=_asset_quality)
    payload = {
        **existing,
        **dict(updates or {}),
        "id": existing.get("id"),
        "ip": existing.get("ip") or ip,
        "createdAt": existing.get("createdAt"),
        "_actorType": (updates or {}).get("_actorType", "user"),
        "_actorId": (updates or {}).get("_actorId", "operator"),
        "_source": (updates or {}).get("_source", "assets-api"),
        "_reason": (updates or {}).get("_reason", "Update CMDB asset"),
        "_correlationId": (updates or {}).get("_correlationId"),
        "_confidence": (updates or {}).get("_confidence"),
    }
    return upsert_managed_asset(payload)
'''

for name, replacement in [
    ("save_assets", save_assets),
    ("migrate_assets", migrate_assets),
    ("get_assets_list", get_assets_list),
    ("upsert_managed_asset", upsert),
    ("update_asset", update),
]:
    source = replace_function(source, name, replacement)

PATH.write_text(source, encoding="utf-8")
print(f"Patched {PATH}")
