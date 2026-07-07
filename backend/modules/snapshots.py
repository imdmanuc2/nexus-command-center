import json
from pathlib import Path

SNAPSHOT_DIR = Path("backend/data/snapshots")


def list_snapshots():
    files = sorted(SNAPSHOT_DIR.glob("*.json"))
    return {
        "snapshots": [
            {"file": f.name, "createdAt": f.stem}
            for f in files
        ]
    }


def get_snapshot(file_name):
    safe_name = Path(file_name).name
    path = SNAPSHOT_DIR / safe_name

    if not path.exists():
        return {"error": "Snapshot not found"}

    return json.loads(path.read_text())
