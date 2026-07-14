from backend.connectors import miningcore


def summary():
    try:
        return miningcore.summary()
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "poolId": "bch",
            "workerCount": 0,
            "workers": [],
            "totalHashrate": 0,
            "sharesPerSecond": 0
        }


def workers():
    data = summary()
    return {
        "status": data.get("status"),
        "poolId": data.get("poolId"),
        "workerCount": data.get("workerCount"),
        "workers": data.get("workers", [])
    }
