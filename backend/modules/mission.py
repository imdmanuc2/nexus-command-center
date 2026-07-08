from backend.modules import mining, discovery, event_engine


def status():
    workers_payload = mining.workers()
    workers = workers_payload.get("workers", [])

    total_hashrate = sum(float(w.get("hashrate") or 0) for w in workers)
    online_workers = len([w for w in workers if float(w.get("hashrate") or 0) > 0])

    scan = discovery.scan()
    systems = scan.get("systems", [])

    events = event_engine.live()[-50:]
    warnings = len([e for e in events if e.get("severity") == "warning"])
    critical = len([e for e in events if e.get("severity") == "critical"])

    return {
        "overall": "healthy" if critical == 0 else "critical",
        "miners": {
            "online": online_workers,
            "total": len(workers),
            "hashrate": total_hashrate
        },
        "infrastructure": {
            "systems": len(systems),
            "healthy": len(systems)
        },
        "services": {
            "api": "online",
            "miningcore": workers_payload.get("status", "unknown"),
            "stratum": "active" if online_workers > 0 else "idle",
            "discovery": "online"
        },
        "events": {
            "warnings": warnings,
            "critical": critical
        }
    }
