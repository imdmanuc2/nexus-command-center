import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.modules import fleet
from backend.modules import smc_health


DB_PATH = Path("backend/data/telemetry/nexus-telemetry.db")


def _now():
    return datetime.now(timezone.utc)


def _iso(value=None):
    return (value or _now()).isoformat()


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _integer(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _connect():
    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        DB_PATH,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA journal_mode=WAL"
    )

    connection.execute(
        "PRAGMA synchronous=NORMAL"
    )

    return connection


def _initialize(connection):
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS fleet_samples (
            recorded_at TEXT PRIMARY KEY,
            fleet_hashrate REAL NOT NULL,
            shares_per_second REAL NOT NULL,
            coin_count INTEGER NOT NULL,
            pool_count INTEGER NOT NULL,
            active_pool_count INTEGER NOT NULL,
            miner_count INTEGER NOT NULL,
            online_miner_count INTEGER NOT NULL,
            node_count INTEGER NOT NULL,
            online_node_count INTEGER NOT NULL,
            fleet_health REAL NOT NULL,
            warning_count INTEGER NOT NULL,
            critical_count INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS pool_samples (
            recorded_at TEXT NOT NULL,
            pool_id TEXT NOT NULL,
            pool_name TEXT,
            coin TEXT,
            host TEXT,
            mode TEXT,
            visibility TEXT,
            status TEXT,
            worker_count INTEGER NOT NULL,
            hashrate REAL NOT NULL,
            shares_per_second REAL NOT NULL,
            PRIMARY KEY (
                recorded_at,
                pool_id
            )
        );

        CREATE INDEX IF NOT EXISTS idx_pool_samples_pool_time
        ON pool_samples (
            pool_id,
            recorded_at
        );

        CREATE TABLE IF NOT EXISTS miner_samples (
            recorded_at TEXT NOT NULL,
            worker_id TEXT NOT NULL,
            miner_name TEXT,
            asset_ip TEXT,
            coin TEXT,
            pool_id TEXT,
            pool_name TEXT,
            pool_host TEXT,
            hashrate REAL NOT NULL,
            shares_per_second REAL NOT NULL,
            status TEXT,
            PRIMARY KEY (
                recorded_at,
                worker_id
            )
        );

        CREATE INDEX IF NOT EXISTS idx_miner_samples_worker_time
        ON miner_samples (
            worker_id,
            recorded_at
        );

        CREATE TABLE IF NOT EXISTS node_samples (
            recorded_at TEXT NOT NULL,
            node_id TEXT NOT NULL,
            node_name TEXT,
            coin TEXT,
            host TEXT,
            online INTEGER NOT NULL,
            block_height INTEGER,
            headers INTEGER,
            peers INTEGER,
            sync_percent REAL,
            disk_bytes REAL,
            mempool_transactions INTEGER,
            PRIMARY KEY (
                recorded_at,
                node_id
            )
        );

        CREATE INDEX IF NOT EXISTS idx_node_samples_node_time
        ON node_samples (
            node_id,
            recorded_at
        );

        CREATE TABLE IF NOT EXISTS smc_samples (
            recorded_at TEXT NOT NULL,
            instance_id TEXT NOT NULL,
            instance_name TEXT,
            host TEXT,
            status TEXT,
            health_score REAL NOT NULL,
            api_online INTEGER NOT NULL,
            api_latency_ms REAL,
            console_online INTEGER NOT NULL,
            pool_count INTEGER NOT NULL,
            active_pool_count INTEGER NOT NULL,
            connected_miners INTEGER NOT NULL,
            total_hashrate REAL NOT NULL,
            shares_per_second REAL NOT NULL,
            PRIMARY KEY (
                recorded_at,
                instance_id
            )
        );

        CREATE INDEX IF NOT EXISTS idx_smc_samples_instance_time
        ON smc_samples (
            instance_id,
            recorded_at
        );
        """
    )


def collect():
    recorded_at = _iso()

    fleet_payload = fleet.home()
    smc_payload = smc_health.health()

    summary = fleet_payload.get(
        "summary",
        {},
    )

    pools = fleet_payload.get(
        "activePools",
        [],
    ) or []

    miners = fleet_payload.get(
        "topMiners",
        [],
    ) or []

    nodes = fleet_payload.get(
        "nodes",
        [],
    ) or []

    instances = smc_payload.get(
        "instances",
        [],
    ) or []

    connection = _connect()

    try:
        _initialize(connection)

        connection.execute(
            """
            INSERT OR REPLACE INTO fleet_samples (
                recorded_at,
                fleet_hashrate,
                shares_per_second,
                coin_count,
                pool_count,
                active_pool_count,
                miner_count,
                online_miner_count,
                node_count,
                online_node_count,
                fleet_health,
                warning_count,
                critical_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                recorded_at,
                _number(
                    summary.get(
                        "fleetHashrate"
                    )
                ),
                _number(
                    summary.get(
                        "sharesPerSecond"
                    )
                ),
                _integer(
                    summary.get(
                        "coinCount"
                    )
                ),
                _integer(
                    summary.get(
                        "poolCount"
                    )
                ),
                _integer(
                    summary.get(
                        "activePoolCount"
                    )
                ),
                _integer(
                    summary.get(
                        "minerCount"
                    )
                ),
                _integer(
                    summary.get(
                        "onlineMinerCount"
                    )
                ),
                _integer(
                    summary.get(
                        "nodeCount"
                    )
                ),
                _integer(
                    summary.get(
                        "onlineNodeCount"
                    )
                ),
                _number(
                    summary.get(
                        "fleetHealth"
                    )
                ),
                _integer(
                    summary.get(
                        "warningCount"
                    )
                ),
                _integer(
                    summary.get(
                        "criticalCount"
                    )
                ),
            ),
        )

        for pool in pools:
            coin = pool.get("coin")

            if isinstance(coin, dict):
                coin = (
                    coin.get("symbol")
                    or coin.get("type")
                )

            connection.execute(
                """
                INSERT OR REPLACE INTO pool_samples (
                    recorded_at,
                    pool_id,
                    pool_name,
                    coin,
                    host,
                    mode,
                    visibility,
                    status,
                    worker_count,
                    hashrate,
                    shares_per_second
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    recorded_at,
                    str(
                        pool.get("id")
                        or pool.get("name")
                    ),
                    pool.get("name"),
                    coin,
                    pool.get("host"),
                    pool.get("mode"),
                    pool.get("visibility"),
                    pool.get("status"),
                    _integer(
                        pool.get(
                            "workerCount"
                        )
                    ),
                    _number(
                        pool.get(
                            "hashrate"
                        )
                    ),
                    _number(
                        pool.get(
                            "sharesPerSecond"
                        )
                    ),
                ),
            )

        for miner in miners:
            connection.execute(
                """
                INSERT OR REPLACE INTO miner_samples (
                    recorded_at,
                    worker_id,
                    miner_name,
                    asset_ip,
                    coin,
                    pool_id,
                    pool_name,
                    pool_host,
                    hashrate,
                    shares_per_second,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    recorded_at,
                    str(
                        miner.get("workerId")
                        or miner.get("name")
                    ),
                    miner.get("name"),
                    miner.get("assetIp"),
                    miner.get("coin"),
                    miner.get("poolId"),
                    miner.get("poolName"),
                    miner.get("poolHost"),
                    _number(
                        miner.get(
                            "hashrate"
                        )
                    ),
                    _number(
                        miner.get(
                            "sharesPerSecond"
                        )
                    ),
                    miner.get(
                        "status",
                        "online",
                    ),
                ),
            )

        for node in nodes:
            connection.execute(
                """
                INSERT OR REPLACE INTO node_samples (
                    recorded_at,
                    node_id,
                    node_name,
                    coin,
                    host,
                    online,
                    block_height,
                    headers,
                    peers,
                    sync_percent,
                    disk_bytes,
                    mempool_transactions
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    recorded_at,
                    str(
                        node.get("id")
                        or node.get("host")
                        or node.get("name")
                    ),
                    node.get("name"),
                    node.get("coin"),
                    node.get("host"),
                    1 if node.get("online") else 0,
                    node.get("blockHeight"),
                    node.get("headers"),
                    node.get("peers"),
                    node.get("syncPercent"),
                    node.get("diskBytes"),
                    node.get(
                        "mempoolTransactions"
                    ),
                ),
            )

        for instance in instances:
            connection.execute(
                """
                INSERT OR REPLACE INTO smc_samples (
                    recorded_at,
                    instance_id,
                    instance_name,
                    host,
                    status,
                    health_score,
                    api_online,
                    api_latency_ms,
                    console_online,
                    pool_count,
                    active_pool_count,
                    connected_miners,
                    total_hashrate,
                    shares_per_second
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    recorded_at,
                    str(
                        instance.get("id")
                        or instance.get("host")
                        or instance.get("name")
                    ),
                    instance.get("name"),
                    instance.get("host"),
                    instance.get("status"),
                    _number(
                        instance.get(
                            "healthScore"
                        )
                    ),
                    (
                        1
                        if instance.get(
                            "api",
                            {},
                        ).get("online")
                        else 0
                    ),
                    instance.get(
                        "api",
                        {},
                    ).get("latencyMs"),
                    (
                        1
                        if instance.get(
                            "console",
                            {},
                        ).get("online")
                        else 0
                    ),
                    _integer(
                        instance.get(
                            "poolCount"
                        )
                    ),
                    _integer(
                        instance.get(
                            "activePoolCount"
                        )
                    ),
                    _integer(
                        instance.get(
                            "connectedMiners"
                        )
                    ),
                    _number(
                        instance.get(
                            "totalHashrate"
                        )
                    ),
                    _number(
                        instance.get(
                            "sharesPerSecond"
                        )
                    ),
                ),
            )

        connection.commit()

        return {
            "success": True,
            "recordedAt": recorded_at,
            "counts": {
                "fleetSamples": 1,
                "pools": len(pools),
                "miners": len(miners),
                "nodes": len(nodes),
                "smcInstances": len(instances),
            },
            "database": str(DB_PATH),
        }

    finally:
        connection.close()


def _cutoff(hours):
    return _iso(
        _now()
        - timedelta(hours=hours)
    )


def _change(previous, current):
    previous = _number(previous)
    current = _number(current)

    if previous <= 0:
        return None

    return round(
        (
            (current - previous)
            / previous
        ) * 100,
        2,
    )


def _fleet_window(
    connection,
    hours,
):
    rows = connection.execute(
        """
        SELECT *
        FROM fleet_samples
        WHERE recorded_at >= ?
        ORDER BY recorded_at ASC
        """,
        (_cutoff(hours),),
    ).fetchall()

    if not rows:
        return {
            "hours": hours,
            "sampleCount": 0,
            "first": None,
            "latest": None,
            "averages": {},
            "changes": {},
        }

    first = dict(rows[0])
    latest = dict(rows[-1])

    average = connection.execute(
        """
        SELECT
            AVG(fleet_hashrate) AS fleet_hashrate,
            AVG(shares_per_second) AS shares_per_second,
            AVG(online_miner_count) AS online_miner_count,
            AVG(active_pool_count) AS active_pool_count,
            AVG(online_node_count) AS online_node_count,
            AVG(fleet_health) AS fleet_health,
            AVG(warning_count) AS warning_count,
            AVG(critical_count) AS critical_count
        FROM fleet_samples
        WHERE recorded_at >= ?
        """,
        (_cutoff(hours),),
    ).fetchone()

    return {
        "hours": hours,
        "sampleCount": len(rows),
        "first": first,
        "latest": latest,
        "averages": dict(average),
        "changes": {
            "fleetHashratePercent": _change(
                first["fleet_hashrate"],
                latest["fleet_hashrate"],
            ),
            "sharesPerSecondPercent": _change(
                first["shares_per_second"],
                latest["shares_per_second"],
            ),
            "onlineMinerCount": (
                latest["online_miner_count"]
                - first["online_miner_count"]
            ),
            "activePoolCount": (
                latest["active_pool_count"]
                - first["active_pool_count"]
            ),
            "fleetHealthPoints": round(
                latest["fleet_health"]
                - first["fleet_health"],
                2,
            ),
        },
    }


def _pool_windows(
    connection,
    hours,
):
    rows = connection.execute(
        """
        SELECT
            pool_id,
            MAX(pool_name) AS pool_name,
            MAX(coin) AS coin,
            MAX(host) AS host,
            COUNT(*) AS sample_count,
            AVG(hashrate) AS average_hashrate,
            MIN(hashrate) AS minimum_hashrate,
            MAX(hashrate) AS maximum_hashrate,
            AVG(worker_count) AS average_worker_count,
            AVG(shares_per_second) AS average_shares_per_second
        FROM pool_samples
        WHERE recorded_at >= ?
        GROUP BY pool_id
        ORDER BY average_hashrate DESC
        """,
        (_cutoff(hours),),
    ).fetchall()

    results = []

    for row in rows:
        item = dict(row)

        first = connection.execute(
            """
            SELECT hashrate, worker_count
            FROM pool_samples
            WHERE pool_id = ?
              AND recorded_at >= ?
            ORDER BY recorded_at ASC
            LIMIT 1
            """,
            (
                item["pool_id"],
                _cutoff(hours),
            ),
        ).fetchone()

        latest = connection.execute(
            """
            SELECT
                recorded_at,
                hashrate,
                worker_count,
                shares_per_second,
                status
            FROM pool_samples
            WHERE pool_id = ?
              AND recorded_at >= ?
            ORDER BY recorded_at DESC
            LIMIT 1
            """,
            (
                item["pool_id"],
                _cutoff(hours),
            ),
        ).fetchone()

        item["latest"] = (
            dict(latest)
            if latest
            else None
        )

        item["hashrateChangePercent"] = (
            _change(
                first["hashrate"],
                latest["hashrate"],
            )
            if first and latest
            else None
        )

        results.append(item)

    return results


def _smc_windows(
    connection,
    hours,
):
    rows = connection.execute(
        """
        SELECT
            instance_id,
            MAX(instance_name) AS instance_name,
            MAX(host) AS host,
            COUNT(*) AS sample_count,
            AVG(health_score) AS average_health_score,
            MIN(health_score) AS minimum_health_score,
            AVG(api_latency_ms) AS average_api_latency_ms,
            MAX(api_latency_ms) AS maximum_api_latency_ms,
            AVG(total_hashrate) AS average_hashrate,
            AVG(connected_miners) AS average_connected_miners
        FROM smc_samples
        WHERE recorded_at >= ?
        GROUP BY instance_id
        ORDER BY instance_name
        """,
        (_cutoff(hours),),
    ).fetchall()

    results = []

    for row in rows:
        item = dict(row)

        latest = connection.execute(
            """
            SELECT *
            FROM smc_samples
            WHERE instance_id = ?
              AND recorded_at >= ?
            ORDER BY recorded_at DESC
            LIMIT 1
            """,
            (
                item["instance_id"],
                _cutoff(hours),
            ),
        ).fetchone()

        item["latest"] = (
            dict(latest)
            if latest
            else None
        )

        results.append(item)

    return results


def summary():
    connection = _connect()

    try:
        _initialize(connection)

        total_samples = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM fleet_samples
            """
        ).fetchone()["count"]

        first_sample = connection.execute(
            """
            SELECT recorded_at
            FROM fleet_samples
            ORDER BY recorded_at ASC
            LIMIT 1
            """
        ).fetchone()

        latest_sample = connection.execute(
            """
            SELECT recorded_at
            FROM fleet_samples
            ORDER BY recorded_at DESC
            LIMIT 1
            """
        ).fetchone()

        return {
            "generatedAt": _iso(),
            "database": str(DB_PATH),
            "sampleCount": total_samples,
            "firstSampleAt": (
                first_sample["recorded_at"]
                if first_sample
                else None
            ),
            "latestSampleAt": (
                latest_sample["recorded_at"]
                if latest_sample
                else None
            ),
            "windows": {
                "oneHour": _fleet_window(
                    connection,
                    1,
                ),
                "twentyFourHours": _fleet_window(
                    connection,
                    24,
                ),
                "sevenDays": _fleet_window(
                    connection,
                    24 * 7,
                ),
            },
            "pools": {
                "oneHour": _pool_windows(
                    connection,
                    1,
                ),
                "twentyFourHours": _pool_windows(
                    connection,
                    24,
                ),
                "sevenDays": _pool_windows(
                    connection,
                    24 * 7,
                ),
            },
            "smcInstances": {
                "oneHour": _smc_windows(
                    connection,
                    1,
                ),
                "twentyFourHours": _smc_windows(
                    connection,
                    24,
                ),
                "sevenDays": _smc_windows(
                    connection,
                    24 * 7,
                ),
            },
        }

    finally:
        connection.close()


def cleanup(days=30):
    cutoff = _iso(
        _now()
        - timedelta(days=days)
    )

    connection = _connect()

    try:
        _initialize(connection)

        deleted = {}

        for table in (
            "fleet_samples",
            "pool_samples",
            "miner_samples",
            "node_samples",
            "smc_samples",
        ):
            cursor = connection.execute(
                f"""
                DELETE FROM {table}
                WHERE recorded_at < ?
                """,
                (cutoff,),
            )

            deleted[table] = cursor.rowcount

        connection.commit()

        connection.execute(
            "PRAGMA optimize"
        )

        return {
            "success": True,
            "cutoff": cutoff,
            "deleted": deleted,
        }

    finally:
        connection.close()
