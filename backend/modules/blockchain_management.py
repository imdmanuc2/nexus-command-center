from __future__ import annotations

from typing import Any

from backend.services import blockchain_management_service


def catalog(
    _query: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    return blockchain_management_service.catalog()


def deployment_plan(
    data: dict[str, Any],
) -> dict[str, Any]:
    return blockchain_management_service.create_deployment_plan(
        data
    )
