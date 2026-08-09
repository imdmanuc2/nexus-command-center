from __future__ import annotations

import os
from typing import Any

import psycopg
from psycopg.rows import dict_row


EXPECTED_METRICS = {
    "runtime.state",
    "runtime.rpc.reachable",
    "runtime.rpc.healthy",
    "runtime.initial_block_download",
    "runtime.verification_progress",
}


def env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def connect():
    return psycopg.connect(
        host=env("NEXUS_DB_HOST"),
        port=int(env("NEXUS_DB_PORT")),
        dbname=env("NEXUS_DB_NAME"),
        user=env("NEXUS_DB_USER"),
        password=env("NEXUS_DB_PASSWORD"),
        row_factory=dict_row,
    )


def main() -> int:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT asset_id, name, observed_state, last_seen_at
                FROM nexus.assets
                WHERE asset_type = 'blockchain-node'
                  AND (
                    name ILIKE '%Bitcoin Cash%'
                    OR name ILIKE '%BCH%'
                  )
                ORDER BY last_seen_at DESC NULLS LAST
                LIMIT 1
                """
            )
            asset = cur.fetchone()

            if not asset:
                raise SystemExit(
                    "No BCH blockchain-node asset found in Nexus."
                )

            asset_id = asset["asset_id"]

            cur.execute(
                """
                SELECT
                    metric_name,
                    metric_value,
                    metric_unit,
                    status,
                    observed_at
                FROM nexus.current_metrics
                WHERE subject_id = %s
                  AND metric_name = ANY(%s)
                ORDER BY metric_name
                """,
                (
                    asset_id,
                    list(EXPECTED_METRICS),
                ),
            )

            rows = cur.fetchall()

    found = {
        row["metric_name"]
        for row in rows
    }

    missing = EXPECTED_METRICS - found

    print(
        "SBP-028 BCH asset:",
        {
            "assetId": asset["asset_id"],
            "name": asset["name"],
            "observedState": asset["observed_state"],
            "lastSeenAt": asset["last_seen_at"],
        },
    )

    for row in rows:
        print(
            "SBP-028 metric:",
            {
                "metricName": row["metric_name"],
                "metricValue": row["metric_value"],
                "metricUnit": row["metric_unit"],
                "status": row["status"],
                "observedAt": row["observed_at"],
            },
        )

    valid_states = {
        "not-installed",
        "stopped",
        "starting",
        "syncing",
        "healthy",
        "degraded",
    }

    state = str(
        asset["observed_state"]
        or ""
    ).strip().lower()

    if state not in valid_states:
        raise SystemExit(
            "BCH asset observed_state is not normalized: "
            f"{asset['observed_state']!r}"
        )

    if missing:
        raise SystemExit(
            "Missing runtime current metrics: "
            + ", ".join(
                sorted(missing)
            )
        )

    state_metric = next(
        row
        for row in rows
        if row["metric_name"] == "runtime.state"
    )

    if str(
        state_metric["metric_value"]
    ).strip().lower() != state:
        raise SystemExit(
            "runtime.state does not match "
            "asset observed_state."
        )

    print(
        "SBP-028 live Nexus runtime-state acceptance: PASS"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
