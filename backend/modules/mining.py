from backend.connectors import miningcore


def summary():
    try:
        return miningcore.summary()
    except Exception as error:
        return {
            "status": "error",
            "error": str(error),
            "poolId": None,
            "poolCount": 0,
            "activePoolCount": 0,
            "workerCount": 0,
            "coinCount": 0,
            "pools": [],
            "activePools": [],
            "workers": [],
            "coins": [],
            "totalHashrate": 0,
            "sharesPerSecond": 0,
        }


def workers():
    data = summary()

    return {
        "status": data.get("status"),
        "workerCount": data.get("workerCount", 0),
        "workers": data.get("workers", []),
    }


def pools():
    data = summary()

    return {
        "status": data.get("status"),
        "poolCount": data.get("poolCount", 0),
        "activePoolCount": data.get(
            "activePoolCount",
            0,
        ),
        "pools": data.get("pools", []),
        "errors": data.get("errors", []),
    }


def coins():
    data = summary()

    return {
        "status": data.get("status"),
        "coinCount": data.get("coinCount", 0),
        "coins": data.get("coins", []),
    }
