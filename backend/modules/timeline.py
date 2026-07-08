from backend.core.graph_diff import diff_latest


def latest():
    diff = diff_latest()

    return {
        "status": diff.get("status"),
        "timestamp": diff.get("toSnapshot"),
        "events": diff.get("changes", [])
    }
