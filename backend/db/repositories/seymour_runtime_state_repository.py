from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

try:
    from psycopg.types.json import Jsonb
except ImportError:
    Jsonb = None


SOURCE = "seymour-runtime-state"

VALID_STATES = {
    "not-installed",
    "stopped",
    "starting",
    "syncing",
    "healthy",
    "degraded",
}


def _now() -> datetime:
    return datetime.now(UTC)


def _metric_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def _asset_runtime(asset: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    telemetry = (
        asset.get("telemetry")
        if isinstance(asset.get("telemetry"), dict)
        else {}
    )

    operational = (
        asset.get("operationalState")
        if isinstance(asset.get("operationalState"), dict)
        else telemetry.get("operationalState")
        if isinstance(telemetry.get("operationalState"), dict)
        else {}
    )

    state = (
        asset.get("runtimeState")
        or telemetry.get("runtimeState")
        or telemetry.get("operationalStateName")
        or operational.get("state")
    )

    if state is not None:
        state = str(state).strip().lower()

    values = {
        "state": state,
        "reason": (
            telemetry.get("runtimeStateReason")
            or operational.get("reason")
        ),
        "rpcReachable": (
            telemetry.get("runtimeRpcReachable")
            if "runtimeRpcReachable" in telemetry
            else operational.get("rpcReachable")
        ),
        "rpcHealthy": (
            telemetry.get("runtimeRpcHealthy")
            if "runtimeRpcHealthy" in telemetry
            else operational.get("rpcHealthy")
        ),
        "initialBlockDownload": (
            telemetry.get("runtimeInitialBlockDownload")
            if "runtimeInitialBlockDownload" in telemetry
            else operational.get("initialBlockDownload")
        ),
        "verificationProgress": (
            telemetry.get("runtimeVerificationProgress")
            if "runtimeVerificationProgress" in telemetry
            else operational.get("verificationProgress")
        ),
    }

    return state, values


def _upsert_metric(
    cur,
    *,
    subject_id: str,
    metric_name: str,
    value: Any,
    unit: str | None,
    status: str,
    observed_at: datetime,
    metadata: dict[str, Any],
) -> None:
    metric_value = _metric_value(value)
    if metric_value is None:
        return

    # Nexus current_metrics has existed in multiple schema revisions.
    # Prefer the canonical columns used by SBP-018, then fall back to
    # the minimal compatible set if metadata/source columns are absent.
    attempts = [
        (
            """
            INSERT INTO nexus.current_metrics(
                subject_id,
                metric_name,
                metric_value,
                metric_unit,
                status,
                observed_at,
                source,
                metadata
            )
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (subject_id, metric_name)
            DO UPDATE SET
                metric_value = EXCLUDED.metric_value,
                metric_unit = EXCLUDED.metric_unit,
                status = EXCLUDED.status,
                observed_at = EXCLUDED.observed_at,
                source = EXCLUDED.source,
                metadata = EXCLUDED.metadata
            """,
            (
                subject_id,
                metric_name,
                metric_value,
                unit,
                status,
                observed_at,
                SOURCE,
                Jsonb(metadata) if Jsonb else metadata,
            ),
        ),
        (
            """
            INSERT INTO nexus.current_metrics(
                subject_id,
                metric_name,
                metric_value,
                metric_unit,
                status,
                observed_at
            )
            VALUES(%s,%s,%s,%s,%s,%s)
            ON CONFLICT (subject_id, metric_name)
            DO UPDATE SET
                metric_value = EXCLUDED.metric_value,
                metric_unit = EXCLUDED.metric_unit,
                status = EXCLUDED.status,
                observed_at = EXCLUDED.observed_at
            """,
            (
                subject_id,
                metric_name,
                metric_value,
                unit,
                status,
                observed_at,
            ),
        ),
    ]

    last_error = None
    for sql, params in attempts:
        try:
            cur.execute(sql, params)
            return
        except Exception as exc:
            last_error = exc
            # Clear only the statement error; the caller's transaction
            # remains authoritative. Psycopg savepoints are not used here,
            # so only retry on undefined-column style failures when possible.
            if getattr(exc, "sqlstate", None) not in {"42703", "42P10"}:
                raise

    if last_error:
        raise last_error


def project_document(
    cur,
    document: dict[str, Any],
) -> int:
    assets = (
        document.get("assets")
        if isinstance(document, dict)
        else None
    )

    if not isinstance(assets, list):
        return 0

    written = 0
    observed_at = _now()

    for asset in assets:
        if not isinstance(asset, dict):
            continue

        if asset.get("providerId") != "bitcoin-cash-mainnet":
            continue

        subject_id = asset.get("assetId")
        if not subject_id:
            continue

        state, runtime = _asset_runtime(asset)

        if state not in VALID_STATES:
            continue

        # Make the normalized runtime state first-class on the CMDB asset.
        cur.execute(
            """
            UPDATE nexus.assets
            SET
                observed_state = %s,
                last_seen_at = %s
            WHERE asset_id = %s
            """,
            (
                state,
                observed_at,
                subject_id,
            ),
        )

        metric_status = (
            "healthy"
            if state in {"healthy", "syncing", "starting"}
            else state
        )

        metrics = [
            ("runtime.state", state, None),
            (
                "runtime.rpc.reachable",
                runtime.get("rpcReachable"),
                "boolean",
            ),
            (
                "runtime.rpc.healthy",
                runtime.get("rpcHealthy"),
                "boolean",
            ),
            (
                "runtime.initial_block_download",
                runtime.get("initialBlockDownload"),
                "boolean",
            ),
            (
                "runtime.verification_progress",
                runtime.get("verificationProgress"),
                "ratio",
            ),
        ]

        for metric_name, value, unit in metrics:
            if value is None:
                continue

            _upsert_metric(
                cur,
                subject_id=subject_id,
                metric_name=metric_name,
                value=value,
                unit=unit,
                status=metric_status,
                observed_at=observed_at,
                metadata={
                    "runtimeState": state,
                    "reason": runtime.get("reason"),
                    "providerId": asset.get("providerId"),
                    "coin": asset.get("coin"),
                },
            )
            written += 1

    return written
