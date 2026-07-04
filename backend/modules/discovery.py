from datetime import datetime, timezone
from backend.core.discovery import scan_network


def scan():
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "discovery": scan_network()
    }
