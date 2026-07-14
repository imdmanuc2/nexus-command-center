import json
from urllib.parse import urlparse
from urllib.request import urlopen, Request

from backend.core.connector import Connector
from backend.core.assets import migrate_assets


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
    assets = migrate_assets()

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

    Preferred:
      asset.workerId == worker suffix

    Fallback:
      worker 001 -> first mining asset by IP
      worker 002 -> second mining asset by IP
    """
    assets = sorted_mining_assets()

    try:
        index = int(str(name)) - 1
    except Exception:
        index = -1

    explicit = next(
        (asset for asset in assets if str(asset.get("workerId", "")).zfill(3) == str(name).zfill(3)),
        None
    )

    if explicit:
        asset = explicit
    elif index >= 0 and index < len(assets):
        asset = assets[index]
    else:
        return {
            "assetIp": None,
            "assetName": None,
            "displayName": f"ASIC {name}",
            "poolGroup": None,
            "purpose": None,
        }

    return {
        "assetIp": asset.get("ip"),
        "assetName": asset.get("friendlyName") or asset.get("name"),
        "displayName": asset.get("friendlyName") or asset.get("name") or f"ASIC {name}",
        "poolGroup": asset.get("poolGroup"),
        "purpose": asset.get("purpose"),
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

        # MiningCore API compatibility:
        #
        # Some builds return current workers under:
        #   performance.workers
        #
        # Other Seymour MiningCore builds return:
        #   performanceSamples[-1].workers
        #
        # Support both formats so Nexus continues working across upgrades.
        workers = detail.get("performance", {}).get("workers", {}) or {}
        worker_source = "performance"
        sample_timestamp = None

        if not workers:
            samples = detail.get("performanceSamples") or []

            # Ignore malformed samples and choose the newest sample that
            # actually contains worker data.
            valid_samples = [
                sample for sample in samples
                if isinstance(sample, dict)
                and isinstance(sample.get("workers"), dict)
                and sample.get("workers")
            ]

            if valid_samples:
                latest_sample = valid_samples[-1]
                workers = latest_sample.get("workers", {}) or {}
                sample_timestamp = latest_sample.get("created")
                worker_source = "performanceSamples"

        # Additional compatibility fallback for future API variants.
        if not workers:
            direct_workers = detail.get("workers")
            if isinstance(direct_workers, dict):
                workers = direct_workers
                worker_source = "workers"

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
            "workerDataSource": worker_source,
            "workerSampleTimestamp": sample_timestamp,
        }


_default_connector = MiningCoreConnector()


def pool_stats():
    return _default_connector.pool_stats()


def pool_performance():
    return _default_connector.pool_performance()


def summary():
    return _default_connector.summary()
