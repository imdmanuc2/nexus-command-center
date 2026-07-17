
from backend.db.repositories.worker_repository import (
    active_worker_invariant,
    list_active_workers,
    list_workers,
)


def workers():
    records = list_workers()
    active = list_active_workers()
    by_type = {}
    by_status = {}
    by_activity = {}
    matched = 0

    for worker in records:
        worker_type = worker.get("workerType") or "unknown"
        status = worker.get("status") or "unknown"
        activity = worker.get("activityState") or "unknown"

        by_type[worker_type] = by_type.get(worker_type, 0) + 1
        by_status[status] = by_status.get(status, 0) + 1
        by_activity[activity] = by_activity.get(activity, 0) + 1
        matched += int(worker.get("assetMatched") is True)

    return {
        "status": "ok",
        "source": "nexus-postgresql-platform",
        "count": len(records),
        "activeCount": len(active),
        "matchedCount": matched,
        "unmatchedCount": len(records) - matched,
        "byType": by_type,
        "byStatus": by_status,
        "byActivity": by_activity,
        "invariant": active_worker_invariant(),
        "workers": records,
        "activeWorkers": active,
    }
