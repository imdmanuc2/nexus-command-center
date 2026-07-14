import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from backend.core import discovery as discovery_core

ASSETS = Path("backend/data/assets.json")
LAST_SCAN = Path("backend/data/discovery/last_scan.json")

PORT_MAP = {
    8333: ("BTC Blockchain Node", "blockchain-node", "BTC"),
    8332: ("BTC RPC Node", "blockchain-node", "BTC"),
    8334: ("BCH P2P Node", "blockchain-node", "BCH"),
    9002: ("BCH RPC Node", "blockchain-node", "BCH"),
    9333: ("LTC Blockchain Node", "blockchain-node", "LTC"),
    9332: ("LTC RPC Node", "blockchain-node", "LTC"),
    22556: ("DOGE Blockchain Node", "blockchain-node", "DOGE"),
}


def classify(system):
    ports = set(system.get("openPorts", []))

    for port, (role, asset_type, coin) in PORT_MAP.items():
        if port in ports:
            system["primaryRole"] = role
            system["type"] = asset_type
            system["coin"] = coin
            system["purpose"] = "Blockchain"
            system["services"] = system.get("services", [])
            system["services"].append({"name": role, "port": port})
            return system

    return system


def scan_targets(targets):
    result = discovery_core.scan_targets(targets)
    result["systems"] = [classify(s) for s in result.get("systems", [])]

    LAST_SCAN.parent.mkdir(parents=True, exist_ok=True)
    LAST_SCAN.write_text(json.dumps(result, indent=2) + "\n")

    return result


def _load_assets():
    if not ASSETS.exists():
        return []

    data = json.loads(ASSETS.read_text() or "[]")
    if isinstance(data, dict):
        return data.get("assets", [])
    return data


def _save_assets(assets):
    ASSETS.write_text(json.dumps(assets, indent=2) + "\n")


def add_system(system):
    assets = _load_assets()
    ip = system.get("ip")

    existing = next((a for a in assets if a.get("ip") == ip and a.get("type") == system.get("type")), None)
    if existing:
        existing.update({
            "friendlyName": system.get("friendlyName") or existing.get("friendlyName") or system.get("primaryRole"),
            "name": system.get("friendlyName") or existing.get("name") or system.get("primaryRole"),
            "updatedAt": datetime.now(timezone.utc).isoformat()
        })
        _save_assets(assets)
        return existing

    asset = {
        "id": f"asset-{uuid.uuid4().hex[:8]}",
        "name": system.get("friendlyName") or system.get("primaryRole") or f"Node {ip}",
        "friendlyName": system.get("friendlyName") or system.get("primaryRole") or f"Node {ip}",
        "ip": ip,
        "type": system.get("type") or "infrastructure-node",
        "purpose": system.get("purpose") or "Infrastructure",
        "coin": system.get("coin"),
        "primaryRole": system.get("primaryRole"),
        "openPorts": system.get("openPorts", []),
        "services": system.get("services", []),
        "createdAutomatically": False,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }

    assets.append(asset)
    _save_assets(assets)
    return asset
