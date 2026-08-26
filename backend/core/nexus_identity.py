"""Canonical runtime identity for a Nexus Command Center instance."""

from __future__ import annotations

import hashlib
import os
import socket
from pathlib import Path
from typing import Any


_MACHINE_ID_PATH = Path("/etc/machine-id")


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _machine_id() -> str:
    try:
        if _MACHINE_ID_PATH.is_file():
            return _MACHINE_ID_PATH.read_text(
                encoding="utf-8"
            ).strip()
    except OSError:
        pass

    return ""


def _hostname() -> str:
    try:
        return _text(socket.gethostname())
    except OSError:
        return ""


def _derived_instance_id() -> tuple[str, str]:
    """Return stable instance ID and derivation source.

    machine-id is preferred because it is stable across normal reboots and
    address changes. The raw machine-id is never exposed as the Nexus ID.

    Hostname is only a final fallback for environments where machine-id is
    unavailable.
    """

    machine_id = _machine_id()

    if machine_id:
        seed = f"machine-id:{machine_id}"
        source = "machine-id"
    else:
        hostname = _hostname()

        if not hostname:
            raise RuntimeError(
                "Unable to determine Nexus instance identity: "
                "NEXUS_INSTANCE_ID is unset and no stable host "
                "identity is available."
            )

        seed = f"hostname:{hostname.lower()}"
        source = "hostname"

    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]

    return f"nexus-{digest}", source


def runtime_identity() -> dict[str, str]:
    explicit_instance_id = _text(
        os.getenv("NEXUS_INSTANCE_ID")
    )

    if explicit_instance_id:
        instance_id = explicit_instance_id
        identity_source = "environment"
    else:
        instance_id, identity_source = _derived_instance_id()

    hostname = _hostname()

    return {
        "organizationId": _text(
            os.getenv("NEXUS_ORGANIZATION_ID")
        ),
        "organizationName": _text(
            os.getenv("NEXUS_ORGANIZATION_NAME")
        ),
        "siteId": _text(
            os.getenv("NEXUS_SITE_ID")
        ),
        "siteName": _text(
            os.getenv("NEXUS_SITE_NAME")
        ),
        "instanceId": instance_id,
        "instanceName": (
            _text(os.getenv("NEXUS_INSTANCE_NAME"))
            or hostname
            or instance_id
        ),
        "hostname": hostname,
        "identitySource": identity_source,
    }


def require_runtime_scope() -> dict[str, str]:
    """Return identity only when organization and site scope are explicit."""

    identity = runtime_identity()

    missing = []

    if not identity["organizationId"]:
        missing.append("NEXUS_ORGANIZATION_ID")

    if not identity["siteId"]:
        missing.append("NEXUS_SITE_ID")

    if missing:
        raise RuntimeError(
            "Missing Nexus runtime scope: "
            + ", ".join(missing)
        )

    return identity
