from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from backend.transports.models import TransportTarget

_DEFAULT = Path(__file__).resolve().parents[1] / "data" / "private" / "managed_hosts.json"


def _load_profiles() -> list[dict[str, Any]]:
    path = Path(os.environ.get("NEXUS_MANAGED_HOSTS_FILE", str(_DEFAULT)))
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("hosts", data) if isinstance(data, dict) else data


def resolve_target(run: dict[str, Any]) -> TransportTarget:
    payload = run.get("inputPayload") or {}
    requested_transport = str(payload.get("transport") or "ssh").strip().lower()
    asset_id = str(run.get("entityId") or payload.get("assetId") or "").strip()

    # Local is intentionally supported only for the Nexus host itself and package verification.
    if requested_transport == "local":
        if asset_id not in {"nexus-local", "package-028-verification"}:
            raise ValueError("Local transport is restricted to the Nexus host")
        return TransportTarget(asset_id=asset_id, transport="local")

    for profile in _load_profiles():
        if str(profile.get("assetId") or "") == asset_id:
            if not profile.get("enabled", True):
                raise ValueError("Managed host profile is disabled")
            return TransportTarget(
                asset_id=asset_id, transport="ssh",
                host=str(profile.get("host") or ""),
                port=int(profile.get("port") or 22),
                username=str(profile.get("username") or ""),
                identity_file=os.path.expanduser(str(profile.get("identityFile") or "")),
                known_hosts_file=os.path.expanduser(str(profile.get("knownHostsFile") or "")),
            )
    raise ValueError(f"No enabled managed host profile for asset {asset_id}")
