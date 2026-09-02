"""Safe runtime build identity projection for Nexus Command Center."""

from __future__ import annotations

import os


DEFAULT_VERSION = "development"
DEFAULT_REVISION = "unknown"


def _clean(value: str | None, default: str) -> str:
    if not isinstance(value, str):
        return default

    value = value.strip()
    return value or default


def build_identity() -> dict[str, str]:
    """Return public, non-secret build provenance for this Nexus runtime."""

    return {
        "version": _clean(
            os.environ.get("NEXUS_VERSION"),
            DEFAULT_VERSION,
        ),
        "revision": _clean(
            os.environ.get("NEXUS_REVISION"),
            DEFAULT_REVISION,
        ),
    }
