
from backend.db.repositories.worker_repository import (
    active_worker_invariant,
    reconcile_worker_sessions,
)


def reconcile_worker_activity():
    sessions = reconcile_worker_sessions()
    invariant = active_worker_invariant()

    return {
        "status": "ok" if invariant["valid"] else "error",
        "source": "nexus-worker-activity-reconciliation",
        "sessions": sessions,
        "invariant": invariant,
    }
