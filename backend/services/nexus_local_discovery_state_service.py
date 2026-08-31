"""Public host-readable state for Nexus local discovery.

PostgreSQL remains authoritative for the user-controlled discovery setting.
This module mirrors only the minimum non-secret state required by a local
discovery transport adapter.

The projection contains no credentials, private keys, organization/site
metadata, peer permissions, enrollment material, or trust state.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from backend.core.nexus_identity import runtime_identity


DEFAULT_STATE_PATH = Path(
    os.environ.get(
        "NEXUS_LOCAL_DISCOVERY_STATE_PATH",
        "backend/data/runtime/nexus-local-discovery.json",
    )
)

PEER_PORT = 8561
STATE_VERSION = 1


def public_state(enabled: bool) -> dict[str, Any]:
    """Build the minimum public discovery transport state."""

    if not isinstance(enabled, bool):
        raise ValueError(
            "localDiscoveryEnabled must be a boolean"
        )

    identity = runtime_identity()

    return {
        "version": STATE_VERSION,
        "enabled": enabled,
        "instanceId": str(
            identity.get("instanceId") or ""
        ).strip(),
        "name": str(
            identity.get("instanceName") or ""
        ).strip(),
        "port": PEER_PORT,
    }


def write_public_state(
    enabled: bool,
    *,
    path: Path | str | None = None,
) -> dict[str, Any]:
    """Atomically write the non-secret local discovery projection."""

    state = public_state(enabled)

    destination = Path(
        path if path is not None else DEFAULT_STATE_PATH
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = destination.with_name(
        f".{destination.name}.{os.getpid()}.tmp"
    )

    payload = (
        json.dumps(
            state,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )

    try:
        temporary.write_text(
            payload,
            encoding="utf-8",
        )

        os.replace(
            temporary,
            destination,
        )

    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass

    return state
