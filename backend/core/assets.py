"""Compatibility wrapper for the canonical Nexus Asset Manager."""

from backend.core.asset_manager import (
    ASSETS_DB as DB,
    discovery_asset,
    get_asset,
    get_assets_list,
    load_assets as _load_assets_list,
    migrate_assets as _migrate_assets_list,
    normalize_asset,
    now_iso,
    save_assets as _save_assets_list,
    update_asset,
)


def load_assets():
    """Return assets keyed by IP for legacy callers."""

    return {
        asset["ip"]: asset
        for asset in _load_assets_list()
    }


def save_assets(data):
    """Accept either the legacy IP dictionary or canonical list."""

    if isinstance(data, dict):
        assets = []

        for ip, asset in data.items():
            if isinstance(asset, dict):
                assets.append({
                    **asset,
                    "ip": asset.get("ip") or ip,
                })

        _save_assets_list(assets)
        return

    _save_assets_list(data if isinstance(data, list) else [])


def migrate_assets():
    return {
        asset["ip"]: asset
        for asset in _migrate_assets_list()
    }


def discover_asset(system):
    return discovery_asset(system)


def asset_type_from_purpose(purpose):
    text = str(purpose or "").lower()

    if "mining" in text or "asic" in text or "miner" in text:
        return "asic"

    if "node" in text or "blockchain" in text:
        return "blockchain-node"

    if "pool" in text:
        return "pool"

    if "server" in text or "host" in text:
        return "server"

    return "unknown"
