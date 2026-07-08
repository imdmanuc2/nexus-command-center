import json
import random
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("backend/data/events/live.json")

EVENTS = [
    ("share.accepted", "Worker submitted share"),
    ("share.rejected", "Rejected share"),
    ("worker.online", "Worker connected"),
    ("worker.offline", "Worker disconnected"),
    ("pool.blocktemplate", "New block template"),
    ("network.block", "New network block"),
    ("hashrate.change", "Hashrate updated"),
]


def ensure_file():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if not OUT.exists() or not OUT.read_text().strip():
        OUT.write_text("[]")


def live():
    ensure_file()
    return json.loads(OUT.read_text())


def generate_events():
    ensure_file()

    existing = live()
    new_events = []

    for _ in range(random.randint(4, 10)):
        kind, msg = random.choice(EVENTS)

        new_events.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "type": kind,
            "message": msg,
            "severity":
                "warning" if "offline" in kind or "rejected" in kind else
                "success" if "accepted" in kind or "online" in kind else
                "info"
        })

    events = (existing + new_events)[-100:]
    OUT.write_text(json.dumps(events, indent=2) + "\n")
    return events
