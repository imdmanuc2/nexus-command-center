import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

DB = Path("backend/data/assets.json")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_assets():
    if not DB.exists():
        return {}
    return json.loads(DB.read_text())


def save_assets(data):
    DB.write_text(json.dumps(data, indent=2) + "\n")


def asset_type_from_purpose(purpose):
    p = (purpose or "").lower()
    if "mining" in p or "asic" in p or "miner" in p:
        return "asic"
    if "node" in p:
        return "blockchain-node"
    if "pool" in p:
        return "pool-host"
    return "unknown"


def normalize_asset(ip, asset):
    asset = dict(asset or {})

    asset.setdefault("id", f"asset-{str(uuid4())[:8]}")
    asset.setdefault("ip", ip)
    asset.setdefault("name", ip)
    asset.setdefault("friendlyName", asset.get("name", ip))
    asset.setdefault("type", asset_type_from_purpose(asset.get("purpose")))
    asset.setdefault("purpose", "Unknown")
    asset.setdefault("favorite", False)
    asset.setdefault("notes", "")
    asset.setdefault("tags", [])
    asset.setdefault("location", "")
    asset.setdefault("rack", "")
    asset.setdefault("position", "")
    asset.setdefault("manufacturer", "")
    asset.setdefault("model", "")
    asset.setdefault("serialNumber", "")
    asset.setdefault("macAddress", "")
    asset.setdefault("hostname", "")
    asset.setdefault("workerId", "")
    asset.setdefault("poolId", "")
    asset.setdefault("poolHost", "")
    asset.setdefault("poolGroup", "")
    asset.setdefault("createdAutomatically", False)
    asset.setdefault("createdAt", now_iso())
    asset["updatedAt"] = now_iso()

    return asset


def migrate_assets():
    db = load_assets()
    changed = False

    for ip, asset in list(db.items()):
        normalized = normalize_asset(ip, asset)
        if normalized != asset:
            db[ip] = normalized
            changed = True

    if changed:
        save_assets(db)

    return db


def get_asset(ip):
    return migrate_assets().get(ip)


def get_assets_list():
    db = migrate_assets()
    return list(db.values())


def discover_asset(system):
    db = migrate_assets()
    ip = system["ip"]

    if ip not in db:
        role = system.get("primaryRole", "")

        if role == "Full Mining Stack":
            name = f"Mining System {len(db)+1}"
            purpose = "Mining"
        elif "Blockchain" in role:
            name = f"Blockchain Node {len(db)+1}"
            purpose = "Node"
        else:
            name = f"Unknown System {len(db)+1}"
            purpose = "Unknown"

        db[ip] = normalize_asset(ip, {
            "name": name,
            "friendlyName": name,
            "purpose": purpose,
            "createdAutomatically": True
        })

        save_assets(db)

    return db[ip]


def update_asset(ip, updates):
    db = migrate_assets()

    if ip not in db:
        db[ip] = normalize_asset(ip, {
            "name": ip,
            "friendlyName": ip,
            "purpose": "Unknown",
            "createdAutomatically": False
        })

    allowed = [
        "name", "friendlyName", "type", "purpose", "favorite", "notes", "tags",
        "poolGroup", "location", "rack", "position", "manufacturer", "model",
        "serialNumber", "macAddress", "hostname", "workerId", "poolId", "poolHost"
    ]

    for key, value in updates.items():
        if key in allowed:
            db[ip][key] = value

    db[ip] = normalize_asset(ip, db[ip])
    save_assets(db)
    return db[ip]
