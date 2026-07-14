import json
import os
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from backend.core.connector import Connector
from backend.core.assets import migrate_assets


DEFAULT_WALLET = "qqvxl558e962fry35ak5mxrglaa6umet7ysxep57e7"

DEFAULT_INSTANCES = [
    {
        "name": "BCH MiningCore .154",
        "baseUrl": "http://192.168.1.154:4000",
        "wallet": DEFAULT_WALLET,
    },
    {
        "name": "BCH MiningCore .156",
        "baseUrl": "http://192.168.1.156:4000",
        "wallet": DEFAULT_WALLET,
    },
]


def load_instances():
    raw = os.getenv("MININGCORE_INSTANCES_JSON", "").strip()

    if not raw:
        return DEFAULT_INSTANCES

    value = json.loads(raw)

    if not isinstance(value, list) or not value:
        raise RuntimeError(
            "MININGCORE_INSTANCES_JSON must be a non-empty JSON list"
        )

    instances = []

    for item in value:
        if not isinstance(item, dict):
            continue

        base_url = str(
            item.get("baseUrl")
            or item.get("base_url")
            or ""
        ).rstrip("/")

        if not base_url:
            continue

        instances.append({
            "name": (
                item.get("name")
                or f"MiningCore {urlparse(base_url).hostname}"
            ),
            "baseUrl": base_url,
            "wallet": item.get("wallet") or DEFAULT_WALLET,
        })

    if not instances:
        raise RuntimeError("No valid MiningCore instances configured")

    return instances


def fetch_json(base_url, path, timeout=5):
    url = f"{base_url.rstrip('/')}{path}"

    request = Request(
        url,
        headers={
            "User-Agent": "Nexus-MiningCore-Connector/0.2"
        },
    )

    with urlopen(request, timeout=timeout) as response:
        return json.loads(
            response.read().decode("utf-8", errors="ignore")
        )


def miningcore_host(base_url):
    return urlparse(base_url).hostname


def miningcore_port(base_url):
    parsed = urlparse(base_url)

    if parsed.port:
        return parsed.port

    return 443 if parsed.scheme == "https" else 80


def safe_id(value):
    return "".join(
        character if character.isalnum() else "-"
        for character in str(value)
    ).strip("-").lower()


def nexus_pool_id(base_url, native_pool_id):
    return (
        f"pool-"
        f"{safe_id(miningcore_host(base_url))}-"
        f"{miningcore_port(base_url)}-"
        f"{safe_id(native_pool_id)}"
    )


def sorted_mining_assets():
    assets = migrate_assets()
    mining_assets = []

    for ip, asset in assets.items():
        name = str(asset.get("name", "")).lower()
        purpose = str(asset.get("purpose", "")).lower()

        if (
            "miner" in name
            or "mining" in name
            or "asic" in name
            or "nano" in name
            or "mining" in purpose
        ):
            mining_assets.append({
                "ip": ip,
                **asset,
            })

    def sort_key(item):
        return [
            int(part) if part.isdigit() else part
            for part in str(item.get("ip", "")).split(".")
        ]

    mining_assets.sort(key=sort_key)

    return mining_assets


def correlate_worker(worker_name):
    assets = sorted_mining_assets()
    normalized_worker = str(worker_name).zfill(3)

    explicit = next(
        (
            asset
            for asset in assets
            if str(asset.get("workerId", "")).zfill(3)
            == normalized_worker
        ),
        None,
    )

    if explicit:
        asset = explicit
    else:
        try:
            index = int(str(worker_name)) - 1
        except (TypeError, ValueError):
            index = -1

        if 0 <= index < len(assets):
            asset = assets[index]
        else:
            return {
                "assetIp": None,
                "assetName": None,
                "displayName": f"ASIC {worker_name}",
                "poolGroup": None,
                "purpose": None,
            }

    return {
        "assetIp": asset.get("ip"),
        "assetName": (
            asset.get("friendlyName")
            or asset.get("name")
        ),
        "displayName": (
            asset.get("friendlyName")
            or asset.get("name")
            or f"ASIC {worker_name}"
        ),
        "poolGroup": asset.get("poolGroup"),
        "purpose": asset.get("purpose"),
    }


def extract_workers(detail):
    workers = (
        detail.get("performance", {}).get("workers", {})
        or {}
    )

    worker_source = "performance"
    sample_timestamp = None

    if not workers:
        samples = detail.get("performanceSamples") or []

        valid_samples = [
            sample
            for sample in samples
            if isinstance(sample, dict)
            and isinstance(sample.get("workers"), dict)
            and sample.get("workers")
        ]

        if valid_samples:
            latest_sample = valid_samples[-1]

            workers = latest_sample.get("workers", {}) or {}
            worker_source = "performanceSamples"
            sample_timestamp = latest_sample.get("created")

    if not workers:
        direct_workers = detail.get("workers")

        if isinstance(direct_workers, dict):
            workers = direct_workers
            worker_source = "workers"

    return workers, worker_source, sample_timestamp


def pool_mode(pool):
    payout_scheme = (
        pool.get("paymentProcessing", {})
        .get("payoutScheme")
    )

    if str(payout_scheme).upper() == "SOLO":
        return "solo"

    return "public"


def pool_name(pool, host):
    coin = pool.get("coin", {})

    symbol = (
        coin.get("symbol")
        or coin.get("type")
        or pool.get("id")
        or "POOL"
    )

    mode = "Solo" if pool_mode(pool) == "solo" else "Public"

    return f"{str(symbol).upper()} {mode} · {host}"


def load_pool(instance, discovered_pool):
    base_url = instance["baseUrl"]
    host = miningcore_host(base_url)
    api_port = miningcore_port(base_url)

    native_pool_id = str(
        discovered_pool.get("id") or "unknown"
    )

    unique_pool_id = nexus_pool_id(
        base_url,
        native_pool_id,
    )

    wallet = (
        instance.get("wallet")
        or DEFAULT_WALLET
    )

    stats_wrapper = fetch_json(
        base_url,
        f"/api/pools/{native_pool_id}",
    )

    live_pool = (
        stats_wrapper.get("pool")
        or discovered_pool
    )

    pool_stats = live_pool.get("poolStats", {})
    coin = live_pool.get("coin", {})
    network = live_pool.get("networkStats", {})

    miner_detail = {}

    if wallet:
        try:
            miner_detail = fetch_json(
                base_url,
                f"/api/pools/{native_pool_id}/miners/{wallet}",
            )
        except Exception:
            miner_detail = {}

    (
        workers_map,
        worker_source,
        sample_timestamp,
    ) = extract_workers(miner_detail)

    worker_list = []

    for worker_name, data in workers_map.items():
        correlation = correlate_worker(worker_name)

        worker_list.append({
            "workerId": (
                f"{wallet}.{worker_name}"
                if wallet
                else str(worker_name)
            ),
            "name": str(worker_name),
            "workerName": str(worker_name),
            "displayName": correlation["displayName"],
            "assetName": correlation["assetName"],
            "assetIp": correlation["assetIp"],
            "host": host,
            "poolHost": host,
            "poolApiPort": api_port,
            "poolId": unique_pool_id,
            "nativePoolId": native_pool_id,
            "poolName": pool_name(live_pool, host),
            "poolGroup": correlation["poolGroup"],
            "purpose": correlation["purpose"],
            "coin": (
                coin.get("symbol")
                or coin.get("type")
            ),
            "fullName": (
                f"{wallet}.{worker_name}"
                if wallet
                else str(worker_name)
            ),
            "hashrate": float(
                data.get("hashrate") or 0
            ),
            "sharesPerSecond": float(
                data.get("sharesPerSecond") or 0
            ),
            "workerDataSource": worker_source,
            "workerSampleTimestamp": sample_timestamp,
        })

    worker_list.sort(
        key=lambda item: item["hashrate"],
        reverse=True,
    )

    worker_hashrate = sum(
        worker["hashrate"]
        for worker in worker_list
    )

    worker_shares_per_second = sum(
        worker["sharesPerSecond"]
        for worker in worker_list
    )

    pool_hashrate = float(
        pool_stats.get("poolHashrate") or 0
    )

    pool_shares_per_second = float(
        pool_stats.get("sharesPerSecond") or 0
    )

    connected_miners = int(
        pool_stats.get("connectedMiners") or 0
    )

    active = (
        connected_miners > 0
        or pool_hashrate > 0
        or worker_hashrate > 0
    )

    return {
        "id": unique_pool_id,
        "nativePoolId": native_pool_id,
        "name": pool_name(live_pool, host),
        "instanceName": instance.get("name"),
        "host": host,
        "apiPort": api_port,
        "apiBase": base_url,
        "endpoint": (
            f"{base_url}/api/pools/{native_pool_id}"
        ),
        "coin": {
            "symbol": (
                coin.get("symbol")
                or coin.get("type")
                or native_pool_id.upper()
            ),
            "name": (
                coin.get("name")
                or native_pool_id.upper()
            ),
            "family": coin.get("family"),
            "algorithm": coin.get("algorithm"),
        },
        "mode": pool_mode(live_pool),
        "visibility": (
            "private"
            if pool_mode(live_pool) == "solo"
            else "public"
        ),
        "status": "active" if active else "idle",
        "active": active,
        "stratumPorts": [
            int(port)
            for port in (
                live_pool.get("ports") or {}
            ).keys()
        ],
        "feePercent": float(
            live_pool.get("poolFeePercent") or 0
        ),
        "address": live_pool.get("address"),
        "workerCount": (
            len(worker_list)
            or connected_miners
        ),
        "connectedMiners": connected_miners,
        "hashrate": (
            pool_hashrate
            or worker_hashrate
        ),
        "workerHashrate": worker_hashrate,
        "sharesPerSecond": (
            pool_shares_per_second
            or worker_shares_per_second
        ),
        "network": {
            "networkType": network.get("networkType"),
            "networkHashrate": network.get("networkHashrate"),
            "networkDifficulty": network.get(
                "networkDifficulty"
            ),
            "blockHeight": network.get("blockHeight"),
            "connectedPeers": network.get(
                "connectedPeers"
            ),
            "nodeVersion": network.get("nodeVersion"),
            "rewardType": network.get("rewardType"),
            "lastNetworkBlockTime": network.get(
                "lastNetworkBlockTime"
            ),
        },
        "workers": worker_list,
    }


class MiningCoreConnector(Connector):
    def instances(self):
        return load_instances()

    def status(self):
        results = []

        for instance in self.instances():
            try:
                pools = fetch_json(
                    instance["baseUrl"],
                    "/api/pools",
                ).get("pools", [])

                results.append({
                    "name": instance["name"],
                    "connected": True,
                    "endpoint": instance["baseUrl"],
                    "host": miningcore_host(
                        instance["baseUrl"]
                    ),
                    "poolCount": len(pools),
                })

            except Exception as error:
                results.append({
                    "name": instance["name"],
                    "connected": False,
                    "endpoint": instance["baseUrl"],
                    "host": miningcore_host(
                        instance["baseUrl"]
                    ),
                    "poolCount": 0,
                    "message": str(error),
                })

        connected_instances = sum(
            1
            for result in results
            if result["connected"]
        )

        return {
            "name": "MiningCore Fleet",
            "connected": connected_instances > 0,
            "connectedInstances": connected_instances,
            "instanceCount": len(results),
            "instances": results,
        }

    def info(self):
        return {
            "type": "MiningCore Fleet",
            "instances": self.instances(),
        }

    def metrics(self):
        try:
            return self.summary()
        except Exception:
            return {
                "totalHashrate": 0,
                "workerCount": 0,
                "poolCount": 0,
                "activePoolCount": 0,
                "sharesPerSecond": 0,
            }

    def pools(self):
        pools = []
        errors = []

        for instance in self.instances():
            base_url = instance["baseUrl"]

            try:
                discovered_pools = fetch_json(
                    base_url,
                    "/api/pools",
                ).get("pools", [])

            except Exception as error:
                errors.append({
                    "instanceName": instance.get("name"),
                    "endpoint": base_url,
                    "error": str(error),
                })
                continue

            for discovered_pool in discovered_pools:
                try:
                    pools.append(
                        load_pool(
                            instance,
                            discovered_pool,
                        )
                    )

                except Exception as error:
                    errors.append({
                        "instanceName": instance.get("name"),
                        "endpoint": base_url,
                        "nativePoolId": discovered_pool.get(
                            "id"
                        ),
                        "error": str(error),
                    })

        pools.sort(
            key=lambda pool: (
                str(
                    pool.get("coin", {})
                    .get("symbol")
                    or ""
                ),
                str(pool.get("host") or ""),
                str(pool.get("nativePoolId") or ""),
            )
        )

        if pools:
            status = "online"
        elif errors:
            status = "partial"
        else:
            status = "offline"

        return {
            "status": status,
            "poolCount": len(pools),
            "activePoolCount": sum(
                1
                for pool in pools
                if pool["active"]
            ),
            "pools": pools,
            "errors": errors,
        }

    def summary(self):
        pool_payload = self.pools()
        pools = pool_payload["pools"]

        workers = []

        for pool in pools:
            workers.extend(
                pool.get("workers", [])
            )

        workers.sort(
            key=lambda worker: worker["hashrate"],
            reverse=True,
        )

        coins_by_symbol = {}

        for pool in pools:
            symbol = str(
                pool.get("coin", {})
                .get("symbol")
                or "UNKNOWN"
            ).upper()

            coin = coins_by_symbol.setdefault(
                symbol,
                {
                    "symbol": symbol,
                    "name": (
                        pool.get("coin", {})
                        .get("name")
                        or symbol
                    ),
                    "poolCount": 0,
                    "activePoolCount": 0,
                    "workerCount": 0,
                    "hashrate": 0,
                    "sharesPerSecond": 0,
                },
            )

            coin["poolCount"] += 1

            if pool["active"]:
                coin["activePoolCount"] += 1

            coin["workerCount"] += int(
                pool.get("workerCount") or 0
            )

            coin["hashrate"] += float(
                pool.get("hashrate") or 0
            )

            coin["sharesPerSecond"] += float(
                pool.get("sharesPerSecond") or 0
            )

        coins = sorted(
            coins_by_symbol.values(),
            key=lambda coin: coin["symbol"],
        )

        active_pools = [
            pool
            for pool in pools
            if pool["active"]
        ]

        total_hashrate = sum(
            float(pool.get("hashrate") or 0)
            for pool in active_pools
        )

        total_shares_per_second = sum(
            float(pool.get("sharesPerSecond") or 0)
            for pool in active_pools
        )

        return {
            "status": pool_payload["status"],
            "poolId": None,
            "poolCount": len(pools),
            "activePoolCount": len(active_pools),
            "workerCount": len(workers),
            "coinCount": len(coins),
            "totalHashrate": total_hashrate,
            "sharesPerSecond": total_shares_per_second,
            "pools": pools,
            "activePools": active_pools,
            "workers": workers,
            "coins": coins,
            "errors": pool_payload.get("errors", []),
        }


_default_connector = MiningCoreConnector()


def status():
    return _default_connector.status()


def pools():
    return _default_connector.pools()


def summary():
    return _default_connector.summary()
