from datetime import datetime, timezone
from backend.core.discovery import scan_network


def summary():
    scan = scan_network()
    s = scan.get("summary", {})

    alerts = 0
    if s.get("miningSystems", 0) == 0:
        alerts += 1
    if s.get("blockchainNodes", 0) == 0:
        alerts += 1
    if s.get("miningBackends", 0) == 0:
        alerts += 1

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "healthy" if alerts == 0 else "warning",
        "systems": s.get("miningSystems", 0),
        "blockchainNodes": s.get("blockchainNodes", 0),
        "miningBackends": s.get("miningBackends", 0),
        "dashboards": s.get("dashboards", 0),
        "stratumServers": s.get("stratumServers", 0),
        "rpcEndpoints": s.get("rpcEndpoints", 0),
        "alerts": alerts
    }
