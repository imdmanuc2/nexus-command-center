from backend.db.repositories.alert_repository import (
    alert_summary,
    list_alerts,
)


def alerts():
    records = list_alerts(limit=100)
    return {
        "status": "ok",
        "source": "nexus-postgresql-platform-alerts",
        "count": len(records),
        "alerts": records,
    }


def active_alerts():
    records = [
        alert
        for alert in list_alerts(limit=250)
        if alert["status"] in {"open", "acknowledged"}
    ]
    return {
        "status": "ok",
        "source": "nexus-postgresql-platform-alerts",
        "count": len(records),
        "alerts": records,
    }


def summary():
    return {
        "status": "ok",
        "source": "nexus-postgresql-platform-alerts",
        **alert_summary(),
    }
