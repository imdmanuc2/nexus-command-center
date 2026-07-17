from backend.db.repositories.platform_event_repository import (
    event_summary,
    list_events,
)


def events():
    records = list_events(limit=100)
    return {
        "status": "ok",
        "source": "nexus-postgresql-platform-events",
        "count": len(records),
        "events": records,
    }


def recent_events():
    records = list_events(limit=25)
    return {
        "status": "ok",
        "source": "nexus-postgresql-platform-events",
        "count": len(records),
        "events": records,
    }


def summary():
    return {
        "status": "ok",
        "source": "nexus-postgresql-platform-events",
        **event_summary(hours=24),
    }
