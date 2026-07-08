import json
import random
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("backend/data/events/live.json")

EVENTS = [
    ("share.accepted", "Worker submitted share", "success"),
    ("share.rejected", "Rejected share", "warning"),
    ("worker.online", "Worker connected", "success"),
    ("worker.offline", "Worker disconnected", "warning"),
    ("pool.blocktemplate", "New block template", "info"),
    ("network.block", "New network block", "info"),
    ("hashrate.change", "Hashrate updated", "info"),
]


def ensure_file():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if not OUT.exists() or not OUT.read_text().strip():
        OUT.write_text("[]")


def live():
    ensure_file()
    return json.loads(OUT.read_text())


def _load_workers():
    try:
        from backend.modules import mining
        payload = mining.workers()
        return payload.get("workers", [])
    except Exception:
        return []


def _worker_label(worker):
    asset = worker.get("assetName") or worker.get("displayName") or worker.get("name") or "Unknown miner"
    worker_id = worker.get("workerName") or worker.get("workerId") or worker.get("name") or "unknown"
    return asset, worker_id


def generate_events():
    ensure_file()

    existing = live()
    workers = _load_workers()
    new_events = []

    for _ in range(random.randint(4, 10)):
        kind, msg, severity = random.choice(EVENTS)
        worker = random.choice(workers) if workers else {}

        asset_name, worker_id = _worker_label(worker)

        event = {
            "time": datetime.now(timezone.utc).isoformat(),
            "type": kind,
            "message": msg,
            "severity": severity,
            "assetName": asset_name,
            "workerId": worker_id,
            "hashrate": worker.get("hashrate"),
            "sharesPerSecond": worker.get("sharesPerSecond"),
            "poolId": worker.get("poolId"),
            "poolGroup": worker.get("poolGroup"),
            "host": worker.get("host") or worker.get("assetIp") or worker.get("poolHost"),
        }

        if kind.startswith("share.") or kind.startswith("worker.") or kind == "hashrate.change":
            event["message"] = f"{msg} · {asset_name} / Worker {worker_id}"

        new_events.append(event)

    events = (existing + new_events)[-100:]
    OUT.write_text(json.dumps(events, indent=2) + "\n")
    return events
