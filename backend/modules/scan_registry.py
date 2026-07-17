import json
from pathlib import Path

from backend.core import discovery as discovery_core
from backend.core.reconciliation_engine import reconcile_observation


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
    result = dict(system or {})
    ports = {
        int(port)
        for port in result.get("openPorts", [])
        if str(port).isdigit()
    }

    matched = []

    for port, classification in PORT_MAP.items():
        if port in ports:
            matched.append((port, classification))

    if not matched:
        return result

    # Prefer P2P identity over RPC-only identity for display purposes.
    matched.sort(
        key=lambda item: (
            0 if "Blockchain Node" in item[1][0] else 1,
            item[0],
        )
    )

    _, (role, asset_type, coin) = matched[0]

    result["primaryRole"] = role
    result["type"] = asset_type
    result["assetType"] = asset_type
    result["canonicalType"] = asset_type
    result["coin"] = coin
    result["purpose"] = "Blockchain"

    services = list(result.get("services") or [])
    existing = {
        (str(item.get("name")), int(item.get("port") or 0))
        for item in services
        if isinstance(item, dict)
    }

    for port, (service_role, _, _) in matched:
        key = (service_role, port)

        if key not in existing:
            services.append({
                "name": service_role,
                "port": port,
            })

    result["services"] = services
    return result


def scan_targets(targets):
    result = discovery_core.scan_targets(targets)
    result["systems"] = [
        classify(system)
        for system in result.get("systems", [])
    ]

    LAST_SCAN.parent.mkdir(parents=True, exist_ok=True)
    LAST_SCAN.write_text(
        json.dumps(result, indent=2) + "\n"
    )

    return result


def add_system(system):
    classified = classify(system)

    result = reconcile_observation(
        classified,
        source="discovery-add-system",
        observer_id="nexus-discovery",
        approve_new=True,
        actor_id="operator",
    )

    asset = result.get("asset")

    if not asset:
        return {
            "success": False,
            "status": result.get("status"),
            "decision": result.get("decision"),
            "confidence": result.get("confidence"),
            "identity": result.get("identity"),
            "observation": result.get("observation"),
        }

    return asset
