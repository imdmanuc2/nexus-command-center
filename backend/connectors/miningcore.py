import json
from urllib.request import urlopen, Request

from backend.core.connector import Connector


MININGCORE_BASE = "http://192.168.1.154:4000"
POOL_ID = "bch"


def fetch_json(path, timeout=4):
    url = f"{MININGCORE_BASE}{path}"
    req = Request(url, headers={"User-Agent": "Nexus-MiningCore-Connector/0.1"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", errors="ignore"))


class MiningCoreConnector(Connector):
    def status(self):
        try:
            self.pool_stats()
            return {
                "name": "MiningCore",
                "connected": True,
                "message": "Connected",
                "endpoint": MININGCORE_BASE,
                "poolId": POOL_ID
            }
        except Exception as e:
            return {
                "name": "MiningCore",
                "connected": False,
                "message": str(e),
                "endpoint": MININGCORE_BASE,
                "poolId": POOL_ID
            }

    def info(self):
        return {
            "endpoint": MININGCORE_BASE,
            "poolId": POOL_ID,
            "type": "MiningCore"
        }

    def metrics(self):
        try:
            return self.summary()
        except Exception:
            return {
                "totalHashrate": 0,
                "workerCount": 0,
                "sharesPerSecond": 0
            }

    def pool_stats(self):
        return fetch_json(f"/api/pools/{POOL_ID}")

    def pool_performance(self):
        return fetch_json(f"/api/pools/{POOL_ID}/performance")

    def summary(self):
        stats = self.pool_stats()
        perf = self.pool_performance()

        pool = stats.get("pool", {})
        pool_stats = pool.get("poolStats", {})
        top_miners = pool.get("topMiners", [])

        workers = perf.get("performance", {}).get("workers", {})
        worker_list = []

        for name, data in workers.items():
            worker_list.append({
                "name": name,
                "hashrate": data.get("hashrate", 0),
                "sharesPerSecond": data.get("sharesPerSecond", 0),
            })

        if not worker_list and top_miners:
            for idx, miner in enumerate(top_miners, start=1):
                worker_list.append({
                    "name": miner.get("miner", f"miner-{idx}"),
                    "hashrate": miner.get("hashrate", 0),
                    "sharesPerSecond": miner.get("sharesPerSecond", 0),
                })

        worker_list.sort(key=lambda x: x["hashrate"], reverse=True)

        total_hashrate = pool_stats.get("poolHashrate") or sum(w["hashrate"] for w in worker_list)
        total_sps = pool_stats.get("sharesPerSecond") or sum(w["sharesPerSecond"] for w in worker_list)

        return {
            "poolId": POOL_ID,
            "status": "online",
            "pool": stats,
            "workerCount": len(worker_list),
            "workers": worker_list,
            "totalHashrate": total_hashrate,
            "sharesPerSecond": total_sps,
        }


_default_connector = MiningCoreConnector()


def pool_stats():
    return _default_connector.pool_stats()


def pool_performance():
    return _default_connector.pool_performance()


def summary():
    return _default_connector.summary()
