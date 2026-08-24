from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from psycopg.types.json import Jsonb


SOURCE = "seymour-runtime-state"

VALID_STATES = {
    "not-installed",
    "stopped",
    "starting",
    "running",
    "syncing",
    "healthy",
    "degraded",
}


def _now() -> datetime:
    return datetime.now(UTC)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _boolean_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if value in (0, 1):
        return float(value)
    return None


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _asset_runtime(asset: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    telemetry = _dict(asset.get("telemetry"))
    operational = (
        _dict(asset.get("operationalState"))
        or _dict(telemetry.get("operationalState"))
    )

    state = (
        asset.get("runtimeState")
        or telemetry.get("runtimeState")
        or telemetry.get("operationalStateName")
        or operational.get("state")
    )

    if state is not None:
        state = str(state).strip().lower()

    return state, {
        "state": state,
        "reason": telemetry.get("runtimeStateReason") or operational.get("reason"),
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


def _upsert_metric(
    cur,
    *,
    subject_id: str,
    metric_name: str,
    metric_value: float,
    metric_unit: str,
    status: str,
    observed_at: datetime,
    data: dict[str, Any],
) -> None:
    cur.execute(
        """
        INSERT INTO nexus.current_metrics(
            subject_type,
            subject_id,
            metric_name,
            metric_value,
            metric_unit,
            status,
            observed_at,
            dimensions,
            data
        )
        VALUES(
            'blockchain-node',
            %s,%s,%s,%s,%s,%s,
            '{}'::jsonb,
            %s
        )
        ON CONFLICT(subject_type,subject_id,metric_name)
        DO UPDATE SET
            metric_value=EXCLUDED.metric_value,
            metric_unit=EXCLUDED.metric_unit,
            status=EXCLUDED.status,
            observed_at=EXCLUDED.observed_at,
            dimensions=EXCLUDED.dimensions,
            data=EXCLUDED.data
        """,
        (
            subject_id,
            metric_name,
            metric_value,
            metric_unit,
            status,
            observed_at,
            Jsonb(data),
        ),
    )


def project_document(cur, document: dict[str, Any]) -> int:
    assets = document.get("assets")
    if not isinstance(assets, list):
        return 0

    written = 0
    observed_at = _now()

    for asset in assets:
        if not isinstance(asset, dict):
            continue
        provider_id = str(
            asset.get("providerId") or ""
        ).strip()

        if not provider_id:
            continue

        subject_id = str(asset.get("assetId") or "").strip()
        if not subject_id:
            continue

        state, runtime = _asset_runtime(asset)
        if state not in VALID_STATES:
            continue

        observed_patch = {
            "runtimeState": state,
            "runtimeStateReason": runtime.get("reason"),
            "runtimeRpcReachable": runtime.get("rpcReachable"),
            "runtimeRpcHealthy": runtime.get("rpcHealthy"),
            "runtimeInitialBlockDownload": runtime.get("initialBlockDownload"),
            "runtimeVerificationProgress": runtime.get("verificationProgress"),
        }

        cur.execute(
            """
            UPDATE nexus.assets
            SET
                observed_state =
                    COALESCE(observed_state, '{}'::jsonb)
                    || %s,
                last_seen_at = %s
            WHERE asset_id = %s
            """,
            (
                Jsonb(observed_patch),
                observed_at,
                subject_id,
            ),
        )

        candidates = [
            (
                "runtime.rpc.reachable",
                _boolean_number(runtime.get("rpcReachable")),
                "boolean",
            ),
            (
                "runtime.rpc.healthy",
                _boolean_number(runtime.get("rpcHealthy")),
                "boolean",
            ),
            (
                "runtime.initial_block_download",
                _boolean_number(runtime.get("initialBlockDownload")),
                "boolean",
            ),
            (
                "runtime.verification_progress",
                _number(runtime.get("verificationProgress")),
                "ratio",
            ),
        ]

        for metric_name, metric_value, metric_unit in candidates:
            if metric_value is None:
                continue

            _upsert_metric(
                cur,
                subject_id=subject_id,
                metric_name=metric_name,
                metric_value=metric_value,
                metric_unit=metric_unit,
                status=state,
                observed_at=observed_at,
                data={
                    "source": SOURCE,
                    "providerId": provider_id,
                    "coin": asset.get("coin"),
                    "runtimeState": state,
                    "runtimeStateReason": runtime.get("reason"),
                },
            )
            written += 1

    return written
