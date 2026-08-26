"""Runtime Nexus instance registration service."""

from __future__ import annotations

from typing import Any

from backend.core.nexus_identity import (
    require_runtime_scope,
)
from backend.db.repositories import (
    nexus_instance_repository,
)


def register_local_instance(
    identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved = identity or require_runtime_scope()

    return nexus_instance_repository.register_local_instance(
        resolved
    )


def get_local_instance() -> dict[str, Any] | None:
    return nexus_instance_repository.get_local_instance()
