import json
from pathlib import Path

DB = Path("backend/data/assets.json")


def load_assets():
    if not DB.exists():
        return {}
    return json.loads(DB.read_text())


def save_assets(data):
    DB.write_text(json.dumps(data, indent=2))


def get_asset(ip):
    return load_assets().get(ip)


def discover_asset(system):
    db = load_assets()

    ip = system["ip"]

    if ip not in db:

        role = system["primaryRole"]

        if role == "Full Mining Stack":
            name = f"Mining System {len(db)+1}"
            purpose = "Mining"

        elif "Blockchain" in role:
            name = f"Blockchain Node {len(db)+1}"
            purpose = "Node"

        else:
            name = f"Unknown System {len(db)+1}"
            purpose = "Unknown"

        db[ip] = {
            "name": name,
            "purpose": purpose,
            "favorite": False,
            "notes": "",
            "tags": [],
            "createdAutomatically": True
        }

        save_assets(db)

    return db[ip]


def update_asset(ip, updates):
    db = load_assets()

    if ip not in db:
        db[ip] = {
            "name": ip,
            "purpose": "Unknown",
            "favorite": False,
            "notes": "",
            "tags": [],
            "createdAutomatically": False
        }

    allowed = ["name", "purpose", "favorite", "notes", "tags", "poolGroup", "location"]

    for key, value in updates.items():
        if key in allowed:
            db[ip][key] = value

    save_assets(db)
    return db[ip]
