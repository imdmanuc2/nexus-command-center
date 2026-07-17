
from backend.db.repositories.asset_repository import list_assets
from backend.db.repositories.pool_repository import list_pools
from backend.db.repositories.worker_repository import list_active_workers
from backend.db.repositories.workload_repository import list_workloads

ONLINE = {"online", "healthy", "running", "active", "connected"}


def fleet():
    assets = list_assets()
    workers = list_active_workers()
    pools = list_pools()
    workloads = list_workloads()

    asset_types = {}
    worker_types = {}
    workload_types = {}

    for asset in assets:
        key = asset.get("assetType") or "unknown"
        asset_types[key] = asset_types.get(key, 0) + 1

    for worker in workers:
        key = worker.get("workerType") or "unknown"
        worker_types[key] = worker_types.get(key, 0) + 1

    for workload in workloads:
        key = workload.get("workloadType") or "unknown"
        workload_types[key] = workload_types.get(key, 0) + 1

    online_pools = [
        pool
        for pool in pools
        if str(pool.get("status") or "").lower() in ONLINE
    ]

    denominator = len(workers) + len(pools)
    health = (
        round(
            ((len(workers) + len(online_pools)) / denominator) * 100,
            2,
        )
        if denominator
        else 100.0
    )

    matched = sum(
        1 for worker in workers
        if worker.get("assetMatched") is True
    )

    # Pool metrics are authoritative when available.
    pool_hashrate = 0.0
    connected_miners = 0

    for pool in online_pools:
        observed = pool.get("observedState") or {}
        stats = (
            observed.get("poolStats")
            or observed.get("stats")
            or {}
        )
        pool_hashrate += float(
            stats.get("poolHashrate")
            or observed.get("poolHashrate")
            or 0
        )
        connected_miners += int(
            stats.get("connectedMiners")
            or observed.get("connectedMiners")
            or 0
        )

    worker_hashrate = sum(
        float(worker.get("currentHashrate") or 0)
        for worker in workers
        if worker.get("telemetryAvailable")
    )

    return {
        "status": "ok",
        "source": "nexus-postgresql-platform",
        "fleetHealth": health,
        "fleetHashrate": pool_hashrate or worker_hashrate,
        "hashrateUnit": "H/s",
        "assets": {
            "total": len(assets),
            "byType": asset_types,
        },
        "workers": {
            "total": len(workers),
            "active": len(workers),
            "online": len(workers),
            "offline": 0,
            "matched": matched,
            "unmatched": len(workers) - matched,
            "byType": worker_types,
            "distinctActiveAssets": len({
                worker.get("assetId")
                for worker in workers
                if worker.get("assetId")
            }),
            "connectedMinersFromPools": connected_miners,
        },
        "pools": {
            "total": len(pools),
            "online": len(online_pools),
            "offline": len(pools) - len(online_pools),
        },
        "workloads": {
            "total": len(workloads),
            "byType": workload_types,
        },
        "compute": {
            "asicWorkers": worker_types.get("asic", 0),
            "cpuWorkers": worker_types.get("cpu", 0),
            "gpuWorkers": worker_types.get("gpu", 0),
            "fpgaWorkers": worker_types.get("fpga", 0),
            "aiWorkloads": sum(
                count
                for key, count in workload_types.items()
                if str(key).startswith("ai-")
            ),
            "miningWorkloads": workload_types.get(
                "crypto-mining",
                0,
            ),
        },
    }
