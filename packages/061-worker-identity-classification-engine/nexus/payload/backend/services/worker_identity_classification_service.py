"""Canonical worker identity and hardware classification for Nexus.

Mining engines report session identities. This service resolves those sessions
back to physical CMDB assets and derives worker classification from CMDB truth.
"""
from __future__ import annotations

from typing import Any


def _text(value: Any) -> str:
    return str(value or "").strip()


def build_asset_indexes(assets: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    by_id: dict[str, dict[str, Any]] = {}
    by_ip: dict[str, dict[str, Any]] = {}
    by_suffix: dict[str, dict[str, Any]] = {}
    by_hostname: dict[str, dict[str, Any]] = {}
    for asset in assets:
        aid = _text(asset.get("id") or asset.get("assetId"))
        if not aid:
            continue
        by_id[aid] = asset
        metadata = asset.get("metadata") or {}
        legacy = metadata.get("legacy") or {}
        observed = asset.get("observedState") or {}
        for value in (asset.get("ip"), observed.get("ip"), legacy.get("ip")):
            if _text(value): by_ip[_text(value).lower()] = asset
        for value in (asset.get("hostname"), legacy.get("hostname")):
            if _text(value): by_hostname[_text(value).lower()] = asset
        suffix = _text(asset.get("workerId") or legacy.get("workerId")).lower()
        if suffix: by_suffix[suffix] = asset
    return {"byId": by_id, "byIp": by_ip, "bySuffix": by_suffix, "byHostname": by_hostname}


def resolve_worker_asset(*, worker_name: str, remote_host: str, config: dict[str, Any], indexes: dict[str, dict[str, dict[str, Any]]]) -> tuple[dict[str, Any] | None, str, int]:
    worker_name_l = _text(worker_name).lower()
    remote_host_l = _text(remote_host).lower()
    suffix = worker_name_l.rsplit(".", 1)[-1] if "." in worker_name_l else worker_name_l
    mappings = config.get("workerAssetMappings") or {}
    explicit = mappings.get(worker_name) or mappings.get(worker_name_l) or mappings.get(suffix) or mappings.get(remote_host)
    if explicit:
        asset = indexes["byId"].get(_text(explicit))
        if asset: return asset, "operator-configured-worker-map", 100
    asset = indexes["bySuffix"].get(suffix)
    if asset: return asset, "cmdb-worker-suffix", 98
    asset = indexes["byIp"].get(remote_host_l)
    if asset: return asset, "cmdb-remote-host", 95
    return None, "unmatched", 0


def classify_worker(*, worker_name: str, asset: dict[str, Any] | None) -> tuple[str, str, str]:
    text = " ".join([
        _text(worker_name),
        _text((asset or {}).get("assetType") or (asset or {}).get("type")),
        _text((asset or {}).get("primaryRole")),
        _text((asset or {}).get("displayName") or (asset or {}).get("name")),
        " ".join(str(x) for x in ((asset or {}).get("capabilities") or [])),
    ]).lower()
    if any(token in text for token in ("cpu", "virtual machine", "virtual-machine", "x86")):
        return "cpu", "Virtual CPU", "CPU Miner"
    if any(token in text for token in ("gpu", "cuda", "graphics")):
        return "gpu", "GPU", "GPU Miner"
    if "fpga" in text:
        return "fpga", "FPGA", "FPGA Miner"
    return "asic", "ASIC", "ASIC Miner"


def asset_display_name(asset: dict[str, Any] | None, fallback: str) -> str:
    if not asset: return fallback
    return _text(asset.get("displayName") or asset.get("friendlyName") or asset.get("name")) or fallback
