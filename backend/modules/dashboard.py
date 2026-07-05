from datetime import datetime, timezone
from backend.core.discovery import scan_network


def summary():
    scan = scan_network()
    s = scan.get("summary", {})
    systems = scan.get("systems", [])

    health_counts = {
        "healthy": 0,
        "warning": 0,
        "critical": 0
    }

    worst_assets = []

    for system in systems:
        health = system.get("health", {})
        level = health.get("level", "critical")
        health_counts[level] = health_counts.get(level, 0) + 1

        worst_assets.append({
            "ip": system.get("ip"),
            "name": system.get("asset", {}).get("name", system.get("ip")),
            "primaryRole": system.get("primaryRole"),
            "score": health.get("score", 0),
            "level": level,
            "label": health.get("label", "Unknown"),
            "miningGroup": system.get("asset", {}).get("poolGroup", "Unassigned")
        })

    worst_assets.sort(key=lambda x: x["score"])

    alerts = health_counts.get("warning", 0) + health_counts.get("critical", 0)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "healthy" if alerts == 0 else "warning",
        "systems": s.get("miningSystems", 0),
        "blockchainNodes": s.get("blockchainNodes", 0),
        "miningBackends": s.get("miningBackends", 0),
        "dashboards": s.get("dashboards", 0),
        "stratumServers": s.get("stratumServers", 0),
        "rpcEndpoints": s.get("rpcEndpoints", 0),
        "alerts": alerts,
        "health": health_counts,
        "worstAssets": worst_assets[:5]
    }
