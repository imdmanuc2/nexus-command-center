import json
from urllib.parse import urlparse
from urllib.request import urlopen, Request

from backend.core.connector import Connector
from backend.core.assets import load_assets


MININGCORE_BASE = "http://192.168.1.154:4000"
POOL_ID = "bch"
WALLET = "qqvxl558e962fry35ak5mxrglaa6umet7ysxep57e7"


def fetch_json(path, timeout=4):
    url = f"{MININGCORE_BASE}{path}"
    req = Request(url, headers={"User-Agent": "Nexus-MiningCore-Connector/0.1"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", errors="ignore"))


def miningcore_host():
    return urlparse(MININGCORE_BASE).hostname


def sorted_mining_assets():
    assets = load_assets()

    mining_assets = []

    for ip, asset in assets.items():
        name = asset.get("name", "").lower()
        purpose = asset.get("purpose", "").lower()

        if (
            "miner" in name
            or "mining" in name
            or "asic" in name
            or "nano" in name
            or "mining" in purpose
        ):
            mining_assets.append({
                "ip": ip,
                **asset
            })

    mining_assets.sort(key=lambda item: [int(part) if part.isdigit() else part for part in item["ip"].split(".")])

    return mining_assets


def correlate_worker(name):
    """
    Correlates MiningCore worker suffixes like wallet.001 / wallet.002
    to Nexus inventory assets.

    Current lab rule:
      worker 001 -> first discovered mining asset by IP
      worker 002 -> second discovered mining asset by IP

    Future:
      replace this with explicit asset.workerName / asset.workerId mapping.
    """
    assets = sorted_mining_assets()

    try:
        index = int(str(name)) - 1
    except Exception:
        index = -1

    explicit = next((asset for asset in assets if str(asset.get("workerId", "")).zfill(3) == str(name).zfill(3)), None)

    if explicit:
        asset = explicit
    elif index >= 0 and index < len(assets):
        asset = assets[index]
        return {
            "assetIp": asset.get("ip"),
            "assetName": asset.get("name"),
            "displayName": asset.get("name"),
            "poolGroup": asset.get("poolGroup"),
            "purpose": asset.get("purpose"),
        }

    return {
        "assetIp": None,
        "assetName": None,
        "displayName": f"ASIC {name}",
        "poolGroup": None,
        "purpose": None,
    }


class MiningCoreConnector(Connector):
    def status(self):
        try:
            self.pool_stats()
            return {
                "name": "MiningCore",
                "connected": True,
                "message": "Connected",
                "endpoint": MININGCORE_BASE,
                "host": miningcore_host(),
                "poolId": POOL_ID
            }
        except Exception as e:
            return {
                "name": "MiningCore",
                "connected": False,
                "message": str(e),
                "endpoint": MININGCORE_BASE,
                "host": miningcore_host(),
                "poolId": POOL_ID
            }

    def info(self):
        return {
            "endpoint": MININGCORE_BASE,
            "host": miningcore_host(),
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

    def miner_detail(self):
        return fetch_json(f"/api/pools/{POOL_ID}/miners/{WALLET}")

    def summary(self):
        stats = self.pool_stats()
        perf = self.pool_performance()

        pool = stats.get("pool", {})
        pool_stats = pool.get("poolStats", {})

        detail = self.miner_detail()
        workers = detail.get("performance", {}).get("workers", {})

        worker_list = []

        for name, data in workers.items():
            correlation = correlate_worker(name)

            worker_list.append({
                "workerId": f"{WALLET}.{name}",
                "name": name,
                "workerName": name,
                "displayName": correlation["displayName"],
                "assetName": correlation["assetName"],
                "assetIp": correlation["assetIp"],
                "host": miningcore_host(),
                "poolHost": miningcore_host(),
                "poolId": POOL_ID,
                "poolGroup": correlation["poolGroup"],
                "purpose": correlation["purpose"],
                "fullName": f"{WALLET}.{name}",
                "hashrate": data.get("hashrate", 0),
                "sharesPerSecond": data.get("sharesPerSecond", 0),
            })

        worker_list.sort(key=lambda x: x["hashrate"], reverse=True)

        total_hashrate = sum(w["hashrate"] for w in worker_list) or pool_stats.get("poolHashrate", 0)
        total_sps = sum(w["sharesPerSecond"] for w in worker_list) or pool_stats.get("sharesPerSecond", 0)

        return {
            "poolId": POOL_ID,
            "host": miningcore_host(),
            "poolHost": miningcore_host(),
            "endpoint": MININGCORE_BASE,
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
