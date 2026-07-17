"""Compatibility helpers for PostgreSQL-backed CMDB asset writes."""

from __future__ import annotations

from typing import Any

from backend.db.repositories import asset_repository


def find_by_ip(ip: str) -> list[dict[str, Any]]:
    value = str(ip or "").strip()
    if not value:
        return []
    return [asset for asset in asset_repository.list_assets(limit=5000) if asset.get("ip") == value]


def delete_asset(asset_id: str) -> bool:
    from backend.db.connection import transaction

    with transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM nexus.assets WHERE asset_id = %s RETURNING asset_id",
                (asset_id,),
            )
            return cursor.fetchone() is not None
