from __future__ import annotations
from typing import Any
from psycopg.types.json import Jsonb

SOURCE = "seymour-blockchain-manager"

def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}

def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def _boolean_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if value in (0, 1):
        return float(value)
    return None

def _operational_status(asset: dict[str, Any]) -> str:
    telemetry = _dict(asset.get("telemetry"))

    for value in (
        asset.get("status"),
        telemetry.get("lifecycleStatus"),
        telemetry.get("runtimeState"),
    ):
        if value is not None and str(value).strip():
            status = str(value).strip().lower()
            if status in {"running", "online", "active", "healthy", "ready"}:
                return "running"
            if status in {"stopped", "offline", "inactive"}:
                return "stopped"
            return status

    running = telemetry.get("running")
    if isinstance(running, bool):
        return "running" if running else "stopped"

    installed = telemetry.get("installed")
    if installed is False:
        return "not-installed"

    return "unknown"


def metric_candidates(asset: dict[str, Any]) -> list[dict[str, Any]]:
    telemetry = _dict(asset.get("telemetry"))
    telemetry_sync = _dict(telemetry.get("sync"))
    telemetry_rpc = _dict(telemetry.get("rpc"))
    telemetry_data = _dict(telemetry.get("data"))
    sync = _dict(asset.get("sync"))
    snapshot = _dict(sync.get("snapshot"))
    peer_quality = _dict(sync.get("peerQuality"))
    stall = _dict(sync.get("stall"))
    items: list[dict[str, Any]] = []

    def add(name: str, value: float | None, unit: str) -> None:
        if value is not None:
            items.append({"metric_name": name, "metric_value": value, "metric_unit": unit})

    add("running", _boolean_number(telemetry.get("running")), "boolean")
    add("installed", _boolean_number(telemetry.get("installed")), "boolean")
    add("rpc_reachable", _boolean_number(telemetry_rpc.get("reachable")), "boolean")
    add("data_used_bytes", _number(telemetry_data.get("usedBytes")), "bytes")
    add("initial_block_download", _boolean_number(telemetry_sync.get("initialBlockDownload")), "boolean")

    height = telemetry_sync.get("height")
    if height is None:
        height = snapshot.get("height")
    headers = telemetry_sync.get("headers")
    if headers is None:
        headers = snapshot.get("headers")
    progress = telemetry_sync.get("progressPercent")
    if progress is None:
        progress = snapshot.get("progress_percent")
    peers = telemetry.get("peers")
    if peers is None:
        peers = snapshot.get("peers")

    add("block_height", _number(height), "blocks")
    add("header_height", _number(headers), "blocks")
    add("sync_progress", _number(progress), "percent")
    add("peer_count", _number(peers), "peers")
    add("mempool", _number(telemetry.get("mempool")), "bytes")
    add("blocks_remaining", _number(sync.get("blocksRemaining")), "blocks")
    add("blocks_per_second", _number(sync.get("blocksPerSecond")), "blocks_per_second")
    add("peer_quality_score", _number(peer_quality.get("score")), "score")
    add("sync_stalled", _boolean_number(stall.get("stalled")), "boolean")
    return items

def project_asset(cursor, asset: dict[str, Any]) -> int:
    if str(asset.get("assetType")) != "blockchain-node":
        return 0
    asset_id = str(asset.get("assetId") or "").strip()
    if not asset_id:
        return 0
    telemetry = _dict(asset.get("telemetry"))
    status = _operational_status(asset)
    sql = (
        "INSERT INTO nexus.current_metrics("
        "subject_type,subject_id,metric_name,metric_value,metric_unit,status,observed_at,dimensions,data"
        ") VALUES('blockchain-node',%s,%s,%s,%s,%s,NOW(),'{}'::JSONB,%s) "
        "ON CONFLICT(subject_type,subject_id,metric_name) DO UPDATE SET "
        "metric_value=EXCLUDED.metric_value,metric_unit=EXCLUDED.metric_unit,"
        "status=EXCLUDED.status,observed_at=EXCLUDED.observed_at,data=EXCLUDED.data"
    )
    written = 0
    for metric in metric_candidates(asset):
        cursor.execute(sql, (
            asset_id,
            metric["metric_name"],
            metric["metric_value"],
            metric["metric_unit"],
            status,
            Jsonb({
                "source": SOURCE,
                "providerId": asset.get("providerId"),
                "coin": asset.get("coin"),
                "network": asset.get("network"),
            }),
        ))
        written += 1
    return written

def project_document(cursor, document: dict[str, Any]) -> int:
    assets = document.get("assets")
    if not isinstance(assets, list):
        return 0
    return sum(project_asset(cursor, asset) for asset in assets if isinstance(asset, dict))
