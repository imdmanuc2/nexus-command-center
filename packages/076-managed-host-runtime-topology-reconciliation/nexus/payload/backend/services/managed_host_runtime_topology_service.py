from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.db.repositories.asset_repository import (
    list_assets,
)
from backend.db.repositories.relationship_repository import (
    reconcile_topology_relationships,
)


RECONCILIATION_SOURCE = "managed-host-runtime-topology"

COIN_PROVIDER_MAP = {
    "BTC": "bitcoin-mainnet",
    "BCH": "bitcoin-cash-mainnet",
    "XMR": "monero-mainnet",
}


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _observed(asset: dict[str, Any]) -> dict[str, Any]:
    return _dict(asset.get("observedState"))


def _telemetry(asset: dict[str, Any]) -> dict[str, Any]:
    return _dict(_observed(asset).get("telemetry"))


def _sync(asset: dict[str, Any]) -> dict[str, Any]:
    return _dict(_observed(asset).get("sync"))


def _metadata(asset: dict[str, Any]) -> dict[str, Any]:
    return _dict(asset.get("metadata"))


def _provider_id(asset: dict[str, Any]) -> str:
    telemetry = _telemetry(asset)
    sync = _sync(asset)

    value = (
        telemetry.get("providerId")
        or sync.get("providerId")
    )

    if value:
        return _text(value)

    return COIN_PROVIDER_MAP.get(
        _text(asset.get("coin")).upper(),
        "",
    )


def _runtime_app_id(asset: dict[str, Any]) -> str:
    telemetry = _telemetry(asset)
    metadata = _metadata(asset)

    return _text(
        telemetry.get("appId")
        or metadata.get("appId")
        or metadata.get("runtimeId")
    )


def _generated_at(asset: dict[str, Any]) -> str:
    sync = _sync(asset)
    telemetry = _telemetry(asset)

    return _text(
        sync.get("generatedAt")
        or telemetry.get("generatedAt")
        or asset.get("updatedAt")
        or asset.get("createdAt")
    )


def _sort_timestamp(value: str) -> tuple[int, str]:
    if not value:
        return (0, "")

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
        return (
            int(parsed.timestamp() * 1_000_000),
            value,
        )
    except (TypeError, ValueError):
        return (0, value)


def _container_name(
    asset: dict[str, Any],
) -> str:
    telemetry = _telemetry(asset)
    container = _dict(telemetry.get("container"))

    return _text(container.get("name"))


def runtime_identity(
    asset: dict[str, Any],
) -> tuple[str, str]:
    provider_id = _provider_id(asset)
    app_id = _runtime_app_id(asset)

    if provider_id and app_id:
        return (provider_id, app_id)

    # Assets without strong runtime identity retain their stable CMDB ID.
    # canonical_blockchain_runtimes() may later associate legacy records
    # with one unambiguous strong runtime using matching container evidence.
    return (
        provider_id,
        _text(asset.get("id")),
    )


def canonical_blockchain_runtimes(
    assets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    blockchain_assets = [
        asset
        for asset in assets
        if asset.get("assetType") == "blockchain-node"
    ]

    # First establish strong identities from provider + appId.
    strong_groups: dict[
        tuple[str, str],
        list[dict[str, Any]],
    ] = {}

    legacy_assets: list[dict[str, Any]] = []

    for asset in blockchain_assets:
        provider_id = _provider_id(asset)
        app_id = _runtime_app_id(asset)

        if provider_id and app_id:
            strong_groups.setdefault(
                (provider_id, app_id),
                [],
            ).append(asset)
        else:
            legacy_assets.append(asset)

    # Index container names belonging to strong runtime identities.
    #
    # Legacy observations may predate appId capture but still contain the
    # runtime container identity. Only fold a legacy observation into a
    # strong runtime when provider + container name identifies exactly one
    # strong runtime. Ambiguous evidence remains separate.
    strong_container_index: dict[
        tuple[str, str],
        set[tuple[str, str]],
    ] = {}

    for strong_key, members in strong_groups.items():
        provider_id = strong_key[0]

        for member in members:
            container_name = _container_name(member)

            if not container_name:
                continue

            strong_container_index.setdefault(
                (provider_id, container_name),
                set(),
            ).add(strong_key)

    groups = {
        key: list(members)
        for key, members in strong_groups.items()
    }

    for asset in legacy_assets:
        provider_id = _provider_id(asset)
        container_name = _container_name(asset)

        candidates = set()

        if provider_id and container_name:
            candidates = strong_container_index.get(
                (provider_id, container_name),
                set(),
            )

        if len(candidates) == 1:
            strong_key = next(iter(candidates))
            groups.setdefault(
                strong_key,
                [],
            ).append(asset)
            continue

        # No unique strong identity exists. Preserve the CMDB asset as its
        # own logical runtime rather than guessing.
        fallback_key = runtime_identity(asset)

        groups.setdefault(
            fallback_key,
            [],
        ).append(asset)

    canonical: list[dict[str, Any]] = []

    for key, members in groups.items():
        selected = max(
            members,
            key=lambda item: (
                _sort_timestamp(_generated_at(item)),
                _text(item.get("id")),
            ),
        )

        canonical.append({
            "runtimeIdentity": {
                "providerId": key[0],
                "runtimeId": key[1],
            },
            "canonicalAsset": selected,
            "historicalAssetIds": sorted(
                _text(item.get("id"))
                for item in members
                if (
                    _text(item.get("id"))
                    != _text(selected.get("id"))
                )
            ),
            "observationCount": len(members),
        })

    return sorted(
        canonical,
        key=lambda item: (
            item["runtimeIdentity"]["providerId"],
            item["runtimeIdentity"]["runtimeId"],
        ),
    )


def _explicit_host_asset_id(
    asset: dict[str, Any],
) -> str:
    metadata = _metadata(asset)
    telemetry = _telemetry(asset)

    return _text(
        metadata.get("hostAssetId")
        or telemetry.get("hostAssetId")
        or telemetry.get("managedHostAssetId")
    )


def _explicit_storage_asset_id(
    asset: dict[str, Any],
) -> str:
    metadata = _metadata(asset)
    telemetry = _telemetry(asset)
    storage = _dict(telemetry.get("storage"))

    return _text(
        metadata.get("storageAssetId")
        or telemetry.get("storageAssetId")
        or storage.get("assetId")
    )


def _asset_ids(
    assets: list[dict[str, Any]],
) -> set[str]:
    return {
        _text(asset.get("id"))
        for asset in assets
        if _text(asset.get("id"))
    }


def _storage_host_ids(
    asset: dict[str, Any],
) -> list[str]:
    metadata = _metadata(asset)
    observed = _observed(asset)

    candidates: list[Any] = [
        metadata.get("hostAssetId"),
        metadata.get("mountedByHostAssetId"),
        observed.get("hostAssetId"),
    ]

    host_ids = metadata.get("hostAssetIds")

    if isinstance(host_ids, list):
        candidates.extend(host_ids)

    return sorted({
        _text(value)
        for value in candidates
        if _text(value)
    })


def plan_runtime_topology(
    assets: list[dict[str, Any]],
) -> dict[str, Any]:
    known_ids = _asset_ids(assets)

    canonical_runtimes = canonical_blockchain_runtimes(
        assets
    )

    relationships: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    for runtime in canonical_runtimes:
        asset = runtime["canonicalAsset"]

        runtime_asset_id = _text(asset.get("id"))
        host_asset_id = _explicit_host_asset_id(asset)
        storage_asset_id = _explicit_storage_asset_id(
            asset
        )

        unresolved_fields: list[str] = []

        if host_asset_id:
            if host_asset_id in known_ids:
                relationships.append({
                    "sourceType": "asset",
                    "sourceId": runtime_asset_id,
                    "relationshipType": "hosted-on",
                    "targetType": "asset",
                    "targetId": host_asset_id,
                    "confidence": 100.0,
                    "metadata": {
                        "providerId": (
                            runtime[
                                "runtimeIdentity"
                            ]["providerId"]
                        ),
                        "runtimeId": (
                            runtime[
                                "runtimeIdentity"
                            ]["runtimeId"]
                        ),
                        "evidence": "explicit-cmdb-host-reference",
                    },
                })
            else:
                unresolved_fields.append(
                    "hostAssetId-not-found"
                )
        else:
            unresolved_fields.append(
                "hostAssetId"
            )

        if storage_asset_id:
            if storage_asset_id in known_ids:
                relationships.append({
                    "sourceType": "asset",
                    "sourceId": runtime_asset_id,
                    "relationshipType": "uses-storage",
                    "targetType": "asset",
                    "targetId": storage_asset_id,
                    "confidence": 100.0,
                    "metadata": {
                        "providerId": (
                            runtime[
                                "runtimeIdentity"
                            ]["providerId"]
                        ),
                        "runtimeId": (
                            runtime[
                                "runtimeIdentity"
                            ]["runtimeId"]
                        ),
                        "evidence": "explicit-cmdb-storage-reference",
                    },
                })
            else:
                unresolved_fields.append(
                    "storageAssetId-not-found"
                )
        else:
            unresolved_fields.append(
                "storageAssetId"
            )

        if unresolved_fields:
            unresolved.append({
                "assetId": runtime_asset_id,
                "providerId": (
                    runtime[
                        "runtimeIdentity"
                    ]["providerId"]
                ),
                "runtimeId": (
                    runtime[
                        "runtimeIdentity"
                    ]["runtimeId"]
                ),
                "missing": unresolved_fields,
                "historicalAssetIds": (
                    runtime["historicalAssetIds"]
                ),
                "observationCount": (
                    runtime["observationCount"]
                ),
            })

    # Storage -> host relationships are also explicit. Discovery evidence
    # must first reconcile the host/storage objects into the CMDB.
    for asset in assets:
        asset_type = _text(
            asset.get("assetType")
        ).lower()

        if asset_type not in {
            "storage",
            "filesystem",
            "disk",
            "nas",
            "storage-target",
        }:
            continue

        storage_asset_id = _text(asset.get("id"))

        for host_asset_id in _storage_host_ids(asset):
            if host_asset_id not in known_ids:
                continue

            relationships.append({
                "sourceType": "asset",
                "sourceId": host_asset_id,
                "relationshipType": "mounts",
                "targetType": "asset",
                "targetId": storage_asset_id,
                "confidence": 100.0,
                "metadata": {
                    "evidence": "explicit-cmdb-storage-host-reference",
                },
            })

    # Deterministic de-duplication.
    dedup: dict[
        tuple[str, str, str, str, str],
        dict[str, Any],
    ] = {}

    for relationship in relationships:
        key = (
            relationship.get(
                "sourceType",
                "asset",
            ),
            relationship["sourceId"],
            relationship[
                "relationshipType"
            ],
            relationship.get(
                "targetType",
                "asset",
            ),
            relationship["targetId"],
        )

        dedup[key] = relationship

    relationships = [
        dedup[key]
        for key in sorted(dedup)
    ]

    return {
        "canonicalRuntimes": canonical_runtimes,
        "relationships": relationships,
        "relationshipCount": len(relationships),
        "unresolved": unresolved,
        "unresolvedCount": len(unresolved),
    }


def reconcile_managed_host_runtime_topology(
    *,
    dry_run: bool = True,
) -> dict[str, Any]:
    assets = list_assets(limit=5000)

    plan = plan_runtime_topology(assets)

    result = {
        "status": (
            "planned"
            if dry_run
            else "reconciled"
        ),
        "dryRun": dry_run,
        **plan,
    }

    if dry_run:
        return result

    write_result = reconcile_topology_relationships(
        plan["relationships"],
        source=RECONCILIATION_SOURCE,
    )

    result["writeResult"] = write_result

    return result
