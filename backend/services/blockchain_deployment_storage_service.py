from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from backend.executors.blockchain_deployment_executor import (
    DeploymentRequest,
)
from backend.services import cmdb_service
from backend.db.repositories.relationship_repository import (
    list_active_relationships,
)


_ALLOWED_STORAGE_TYPES = frozenset({
    "storage",
    "network-storage",
})


@dataclass(frozen=True, slots=True)
class DeploymentStorageContext:
    storage_asset_id: str
    storage_asset_type: str
    target_asset_id: str
    storage_source: str
    storage_filesystem: str
    storage_mount_path: str


class BlockchainDeploymentStorageService:
    """
    Resolve blockchain deployment storage authority from canonical CMDB.

    Public requests provide only a canonical storage asset ID. Filesystem
    paths, devices, network exports, and mount metadata remain CMDB-owned
    infrastructure state and are never accepted as deployment authority.

    A storage target is authorized only when:

    * the canonical CMDB asset exists with the requested identity;
    * the asset is Nexus-managed;
    * the asset type is storage or network-storage;
    * the asset advertises blockchain-storage capability; and
    * the selected deployment target has an active, approved
      asset --mounts--> asset relationship to the storage asset.
    """

    def __init__(
        self,
        *,
        asset_getter: Callable[
            [str], dict[str, Any]
        ] | None = None,
        relationship_getter: Callable[
            [], list[dict[str, Any]]
        ] | None = None,
    ) -> None:
        self._asset_getter = (
            asset_getter
            or cmdb_service.get_asset
        )
        self._relationship_getter = (
            relationship_getter
            or list_active_relationships
        )

    def resolve(
        self,
        request: DeploymentRequest,
    ) -> DeploymentStorageContext:
        storage_id = str(
            request.storage_target_id or ""
        ).strip()

        target_id = str(
            request.target_asset_id or ""
        ).strip()

        if not storage_id:
            raise ValueError(
                "Blockchain deployment storage target ID is required"
            )

        if not target_id:
            raise ValueError(
                "Blockchain deployment target asset ID is required"
            )

        response = self._asset_getter(
            storage_id
        )

        if not isinstance(response, dict):
            raise ValueError(
                "CMDB returned invalid deployment storage response"
            )

        if response.get("status") != "ok":
            raise ValueError(
                "Blockchain deployment storage target does not exist in CMDB"
            )

        asset = response.get("asset")

        if not isinstance(asset, dict):
            raise ValueError(
                "CMDB returned invalid deployment storage asset"
            )

        canonical_id = str(
            asset.get("id") or ""
        ).strip()

        if canonical_id != storage_id:
            raise ValueError(
                "CMDB deployment storage identity mismatch"
            )

        if not bool(asset.get("managed")):
            raise ValueError(
                "Blockchain deployment storage target is not Nexus-managed"
            )

        asset_type = str(
            asset.get("assetType") or ""
        ).strip()

        if asset_type not in _ALLOWED_STORAGE_TYPES:
            raise ValueError(
                "Blockchain deployment storage target has unsupported asset type"
            )

        capabilities = asset.get(
            "capabilities"
        )

        if not isinstance(capabilities, list):
            capabilities = []

        if "blockchain-storage" not in {
            str(item).strip()
            for item in capabilities
        }:
            raise ValueError(
                "Blockchain deployment storage target is not "
                "classified for blockchain storage"
            )

        relationships = (
            self._relationship_getter()
        )

        if not isinstance(
            relationships,
            list,
        ):
            raise ValueError(
                "CMDB returned invalid storage relationship response"
            )

        authorized = False

        for relationship in relationships:
            if not isinstance(
                relationship,
                dict,
            ):
                continue

            if (
                str(
                    relationship.get(
                        "sourceType"
                    )
                    or ""
                ).strip()
                == "asset"
                and str(
                    relationship.get(
                        "sourceId"
                    )
                    or ""
                ).strip()
                == target_id
                and str(
                    relationship.get(
                        "relationshipType"
                    )
                    or ""
                ).strip()
                == "mounts"
                and str(
                    relationship.get(
                        "targetType"
                    )
                    or ""
                ).strip()
                == "asset"
                and str(
                    relationship.get(
                        "targetId"
                    )
                    or ""
                ).strip()
                == canonical_id
                and str(
                    relationship.get(
                        "status"
                    )
                    or ""
                ).strip()
                == "active"
                and relationship.get(
                    "approved"
                )
                is True
            ):
                authorized = True
                break

        if not authorized:
            raise ValueError(
                "Blockchain deployment storage target is not "
                "authorized for the selected deployment target"
            )

        observed_state = asset.get("observedState")

        if not isinstance(observed_state, dict):
            raise ValueError(
                "CMDB deployment storage target is missing observed state"
            )

        storage_state = observed_state.get("storage")

        if not isinstance(storage_state, dict):
            raise ValueError(
                "CMDB deployment storage target is missing storage state"
            )

        storage_source = str(
            storage_state.get("source") or ""
        ).strip()

        storage_filesystem = str(
            storage_state.get("filesystem") or ""
        ).strip()

        storage_mount_path = str(
            storage_state.get("mountPath") or ""
        ).strip()

        if not storage_source:
            raise ValueError(
                "CMDB deployment storage target is missing physical source"
            )

        if not storage_filesystem:
            raise ValueError(
                "CMDB deployment storage target is missing filesystem"
            )

        return DeploymentStorageContext(
            storage_asset_id=canonical_id,
            storage_asset_type=asset_type,
            target_asset_id=target_id,
            storage_source=storage_source,
            storage_filesystem=storage_filesystem,
            storage_mount_path=storage_mount_path,
        )
