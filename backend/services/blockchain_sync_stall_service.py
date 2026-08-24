from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


STALL_WINDOW_SECONDS = 15 * 60
MINIMUM_HISTORY_SECONDS = 10 * 60

SYNC_PROGRESS_EPSILON = 0.000001
BLOCK_HEIGHT_EPSILON = 0.0

MANAGED_RUNTIME_SOURCE = "seymour-managed-runtime"


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def _movement(
    rows: list[dict[str, Any]],
    *,
    epsilon: float,
) -> bool:
    if len(rows) < 2:
        return False

    values: list[float] = []

    for row in rows:
        value = row.get("metric_value")

        if value is None:
            continue

        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue

    if len(values) < 2:
        return False

    baseline = values[0]

    return any(
        value > baseline + epsilon
        for value in values[1:]
    )


def _history_span_seconds(
    rows: list[dict[str, Any]],
) -> float:
    timestamps = [
        _utc(row.get("observed_at"))
        for row in rows
    ]

    timestamps = [
        value
        for value in timestamps
        if value is not None
    ]

    if len(timestamps) < 2:
        return 0.0

    return max(
        0.0,
        (
            max(timestamps) - min(timestamps)
        ).total_seconds(),
    )


def _latest_age_seconds(
    rows: list[dict[str, Any]],
    *,
    now: datetime,
) -> float | None:
    timestamps = [
        _utc(row.get("observed_at"))
        for row in rows
    ]

    timestamps = [
        value
        for value in timestamps
        if value is not None
    ]

    if not timestamps:
        return None

    return max(
        0.0,
        (
            now - max(timestamps)
        ).total_seconds(),
    )


def evaluate_sync_stall(
    *,
    syncing: bool,
    rpc_available: bool,
    sync_progress_rows: list[dict[str, Any]],
    block_height_rows: list[dict[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any]:
    """
    Determine whether an actively syncing blockchain runtime has
    stopped making measurable synchronization progress.

    The detector intentionally does not classify one or two identical
    samples as a stall. A runtime must have sufficient historical
    coverage across the configured observation window.

    Progress in either block height or synchronization percentage is
    sufficient to keep the runtime in the progressing state.
    """

    current_time = _utc(now) or datetime.now(timezone.utc)

    all_rows = (
        list(sync_progress_rows)
        + list(block_height_rows)
    )

    result: dict[str, Any] = {
        "evaluated": False,
        "stalled": False,
        "reason": "not-evaluated",
        "windowSeconds": STALL_WINDOW_SECONDS,
        "minimumHistorySeconds": MINIMUM_HISTORY_SECONDS,
        "historySpanSeconds": 0.0,
        "latestSampleAgeSeconds": None,
        "syncProgressAdvanced": False,
        "blockHeightAdvanced": False,
    }

    if not syncing:
        result["reason"] = "runtime-not-syncing"
        return result

    if not rpc_available:
        result["reason"] = "rpc-not-available"
        return result

    if not all_rows:
        result["reason"] = "no-history"
        return result

    history_span = max(
        _history_span_seconds(sync_progress_rows),
        _history_span_seconds(block_height_rows),
    )

    latest_age = _latest_age_seconds(
        all_rows,
        now=current_time,
    )

    result["historySpanSeconds"] = history_span
    result["latestSampleAgeSeconds"] = latest_age

    if latest_age is None:
        result["reason"] = "no-timestamped-history"
        return result

    #
    # If telemetry itself is older than the stall window, this detector
    # must not reinterpret stale telemetry as a synchronization stall.
    # Connectivity/telemetry freshness is a different health condition.
    #
    if latest_age > STALL_WINDOW_SECONDS:
        result["reason"] = "history-stale"
        return result

    if history_span < MINIMUM_HISTORY_SECONDS:
        result["reason"] = "insufficient-history"
        return result

    progress_advanced = _movement(
        sync_progress_rows,
        epsilon=SYNC_PROGRESS_EPSILON,
    )

    height_advanced = _movement(
        block_height_rows,
        epsilon=BLOCK_HEIGHT_EPSILON,
    )

    result["evaluated"] = True
    result["syncProgressAdvanced"] = progress_advanced
    result["blockHeightAdvanced"] = height_advanced

    if progress_advanced or height_advanced:
        result["reason"] = "progress-observed"
        return result

    #
    # History has covered the minimum evaluation period without
    # measurable movement. Require the full configured stall window
    # before declaring the runtime stalled.
    #
    if history_span < STALL_WINDOW_SECONDS:
        result["reason"] = "stall-window-not-reached"
        return result

    result["stalled"] = True
    result["reason"] = "no-progress-within-stall-window"

    return result
