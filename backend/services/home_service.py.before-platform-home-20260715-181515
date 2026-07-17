"""
Platform Home Service

Aggregates the shared Platform services into a lightweight
dashboard payload for Home V2.

IMPORTANT

This service never performs HTTP requests.

It calls shared Python services directly.

All data ultimately comes from PostgreSQL-backed repositories
or approved shared live services.
"""

from datetime import datetime, timezone

from backend.services import fleet_service
from backend.services import worker_service
from backend.services import pool_service
from backend.services import metrics_service

# These will exist shortly
try:
    from backend.services import node_service
except Exception:
    node_service = None

try:
    from backend.services import miningcore_service
except Exception:
    miningcore_service = None

try:
    from backend.services import alert_service
except Exception:
    alert_service = None

try:
    from backend.services import event_service
except Exception:
    event_service = None


def home():

    fleet = fleet_service.fleet()

    workers = worker_service.workers()

    pools = pool_service.pools()

    metrics = metrics_service.current()

    nodes = (
        node_service.nodes()
        if node_service else
        {
            "status": "pending",
            "count": 0,
            "nodes": []
        }
    )

    miningcore = (
        miningcore_service.summary()
        if miningcore_service else
        {
            "status": "pending",
            "instances": []
        }
    )

    alerts = (
        alert_service.summary()
        if alert_service else
        {
            "count": 0,
            "alerts": []
        }
    )

    events = (
        event_service.summary()
        if event_service else
        {
            "count": 0,
            "events": []
        }
    )

    return {

        "status": "ok",

        "source": "nexus-postgresql-platform",

        "generatedAt": datetime.now(timezone.utc).isoformat(),

        "summary": fleet,

        "workers": workers,

        "pools": pools,

        "nodes": nodes,

        "miningCore": miningcore,

        "alerts": alerts,

        "events": events,

        "metrics": metrics

    }