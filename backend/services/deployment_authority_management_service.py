"""Explicit deployment authority management.

This service owns operator-controlled promotion of canonical CMDB
infrastructure into the blockchain deployment authority model.

Architectural rules:

* The Nexus CMDB remains the canonical source of truth.
* Deployment platform identity is explicit and is never inferred.
* Only registered deployment platform profiles may be assigned.
* Only existing managed CMDB assets may receive deployment authority.
* Planning performs no persistence.
* Storage discovery is evidence, not deployment authority.
* Storage enrollment requires explicit approval.
* Filesystem paths/devices/exports remain discovery evidence and are
  never accepted as deployment-request authority.
"""

from __future__ import annotations

from typing import Any, Callable

from backend.core.asset_manager import (
    upsert_managed_asset,
)
from backend.db.repositories.asset_repository import (
    get_asset,
)
from backend.services.blockchain_target_platform import (
    resolve_target_platform_profile,
)
from backend.services.managed_host_storage_enrollment_service import (
    enroll_storage_candidate,
    storage_candidates_from_discovery,
)
from backend.db.repositories.relationship_repository import revoke_relationship


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


class DeploymentAuthorityManagementService:
    """Manage explicit CMDB-backed blockchain deployment authority."""

    def __init__(
        self,
        *,
        asset_getter: Callable[[str], dict[str, Any] | None] | None = None,
        asset_writer: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        storage_candidate_provider: Callable[
            [dict[str, Any]],
            list[dict[str, Any]],
        ] | None = None,
        storage_enroller: Callable[..., dict[str, Any]] | None = None,
        platform_resolver: Callable[[str], Any] | None = None,
        relationship_revoker=None,
    ):
        self._asset_getter = asset_getter or get_asset
        self._asset_writer = asset_writer or upsert_managed_asset
        self._storage_candidate_provider = (
            storage_candidate_provider
            or storage_candidates_from_discovery
        )
        self._storage_enroller = (
            storage_enroller
            or enroll_storage_candidate
        )
        self._platform_resolver = (
            platform_resolver
            or resolve_target_platform_profile
        )
        self._relationship_revoker = (
            relationship_revoker
            or revoke_relationship
        )

    def _canonical_managed_asset(
        self,
        asset_id: str,
    ) -> dict[str, Any]:
        canonical_id = _text(asset_id)

        if not canonical_id:
            raise ValueError(
                "Deployment authority requires assetId."
            )

        asset = self._asset_getter(canonical_id)

        if not isinstance(asset, dict):
            raise ValueError(
                "Deployment authority requires an existing "
                "canonical CMDB asset."
            )

        if _text(asset.get("id")) != canonical_id:
            raise ValueError(
                "CMDB asset identity does not match requested assetId."
            )

        if not bool(asset.get("managed")):
            raise ValueError(
                "Deployment authority requires a managed CMDB asset."
            )

        return asset

    def classify_deployment_platform(
        self,
        *,
        asset_id: str,
        platform_id: str,
        actor_id: str,
        execute: bool = False,
    ) -> dict[str, Any]:
        """Plan or execute explicit deployment-platform classification."""

        asset = self._canonical_managed_asset(
            asset_id
        )

        platform_id = _text(platform_id)
        actor_id = _text(actor_id)

        if not platform_id:
            raise ValueError(
                "Deployment platform is required."
            )

        if not actor_id:
            raise ValueError(
                "Deployment platform classification requires actorId."
            )

        profile = self._platform_resolver(
            platform_id
        )

        canonical_platform_id = _text(
            getattr(profile, "platform_id", "")
        )

        if canonical_platform_id != platform_id:
            raise ValueError(
                "Resolved deployment platform identity does not "
                "match requested platformId."
            )

        current_platform_id = _text(
            asset.get("deploymentPlatformId")
        )

        payload = {
            **asset,
            "deploymentPlatformId": platform_id,
            "_actorType": "user",
            "_actorId": actor_id,
            "_source": "deployment-authority-management",
            "_reason": (
                "Explicitly classify managed CMDB asset "
                "for blockchain deployment"
            ),
        }

        if not execute:
            return {
                "status": "planned",
                "executable": True,
                "executionPerformed": False,
                "assetId": _text(asset.get("id")),
                "currentPlatformId": current_platform_id,
                "deploymentPlatformId": platform_id,
                "asset": payload,
            }

        persisted = self._asset_writer(
            payload
        )

        if not isinstance(persisted, dict):
            raise RuntimeError(
                "Deployment platform classification did not "
                "return a persisted CMDB asset."
            )

        if _text(persisted.get("id")) != _text(
            asset.get("id")
        ):
            raise RuntimeError(
                "Persisted CMDB asset identity changed during "
                "deployment platform classification."
            )

        if _text(
            persisted.get("deploymentPlatformId")
        ) != platform_id:
            raise RuntimeError(
                "Persisted CMDB deployment platform does not "
                "match requested platformId."
            )

        return {
            "status": "classified",
            "executable": True,
            "executionPerformed": True,
            "assetId": _text(persisted.get("id")),
            "previousPlatformId": current_platform_id,
            "deploymentPlatformId": platform_id,
            "asset": persisted,
        }

    def list_storage_candidates(
        self,
        *,
        asset_id: str,
    ) -> dict[str, Any]:
        """Return non-authoritative storage candidates for a managed host."""

        asset = self._canonical_managed_asset(
            asset_id
        )

        candidates = self._storage_candidate_provider(
            asset
        )

        if not isinstance(candidates, list):
            raise RuntimeError(
                "Storage candidate provider must return a list."
            )

        return {
            "status": "ok",
            "hostAssetId": _text(asset.get("id")),
            "candidateCount": len(candidates),
            "candidates": candidates,
            "executionPerformed": False,
        }

    def enroll_storage(
        self,
        *,
        asset_id: str,
        storage_asset_id: str,
        actor_id: str,
        approved: bool = False,
        execute: bool = False,
    ) -> dict[str, Any]:
        """Plan or execute enrollment of one discovered storage candidate."""

        asset = self._canonical_managed_asset(
            asset_id
        )

        storage_asset_id = _text(
            storage_asset_id
        )
        actor_id = _text(actor_id)

        if not storage_asset_id:
            raise ValueError(
                "Storage enrollment requires storageAssetId."
            )

        if not actor_id:
            raise ValueError(
                "Storage enrollment requires actorId."
            )

        if not approved:
            return {
                "status": "approval-required",
                "approved": False,
                "executionPerformed": False,
                "hostAssetId": _text(asset.get("id")),
                "storageAssetId": storage_asset_id,
            }

        candidates = self._storage_candidate_provider(
            asset
        )

        if not isinstance(candidates, list):
            raise RuntimeError(
                "Storage candidate provider must return a list."
            )

        matches = [
            candidate
            for candidate in candidates
            if isinstance(candidate, dict)
            and _text(candidate.get("assetId"))
            == storage_asset_id
            and _text(candidate.get("hostAssetId"))
            == _text(asset.get("id"))
        ]

        if len(matches) != 1:
            raise ValueError(
                "Storage enrollment requires exactly one current "
                "discovery candidate matching the selected host "
                "and storageAssetId."
            )

        candidate = {
            **matches[0],
            "approved": True,
        }

        result = self._storage_enroller(
            candidate,
            actor_id=actor_id,
            execute=bool(execute),
        )

        if not isinstance(result, dict):
            raise RuntimeError(
                "Storage enrollment did not return a result object."
            )

        return {
            **result,
            "approved": True,
            "hostAssetId": _text(asset.get("id")),
            "storageAssetId": storage_asset_id,
            "executionPerformed": bool(execute),
        }

    def revoke_deployment_platform(
        self,
        *,
        asset_id: str,
        actor_id: str,
        execute: bool = False,
    ) -> dict[str, Any]:
        """Plan or revoke explicit deployment-platform authority."""

        asset = self._canonical_managed_asset(
            asset_id
        )

        actor_id = _text(actor_id)

        if not actor_id:
            raise ValueError(
                "Deployment platform revocation requires actorId."
            )

        current_platform_id = _text(
            asset.get("deploymentPlatformId")
        )

        if not current_platform_id:
            raise ValueError(
                "Managed CMDB asset has no deployment "
                "platform authority to revoke."
            )

        payload = {
            **asset,
            "deploymentPlatformId": "",
            "_actorType": "user",
            "_actorId": actor_id,
            "_source": "deployment-authority-management",
            "_reason": (
                "Explicitly revoke managed CMDB asset "
                "blockchain deployment platform authority"
            ),
        }

        if not execute:
            return {
                "status": "planned",
                "executable": True,
                "executionPerformed": False,
                "assetId": _text(
                    asset.get("id")
                ),
                "previousPlatformId": (
                    current_platform_id
                ),
                "deploymentPlatformId": "",
                "asset": payload,
            }

        persisted = self._asset_writer(
            payload
        )

        if not isinstance(
            persisted,
            dict,
        ):
            raise RuntimeError(
                "Deployment platform revocation did not "
                "return a persisted CMDB asset."
            )

        if _text(
            persisted.get("id")
        ) != _text(
            asset.get("id")
        ):
            raise RuntimeError(
                "Persisted CMDB asset identity changed "
                "during deployment platform revocation."
            )

        if _text(
            persisted.get(
                "deploymentPlatformId"
            )
        ):
            raise RuntimeError(
                "Deployment platform authority remained "
                "after revocation."
            )

        return {
            "status": "revoked",
            "executable": True,
            "executionPerformed": True,
            "assetId": _text(
                persisted.get("id")
            ),
            "previousPlatformId": (
                current_platform_id
            ),
            "deploymentPlatformId": "",
            "asset": persisted,
        }

    def revoke_storage_authority(
        self,
        *,
        asset_id: str,
        storage_asset_id: str,
        actor_id: str,
        execute: bool = False,
    ) -> dict[str, Any]:
        """Plan or revoke host-to-storage deployment authority."""

        asset = self._canonical_managed_asset(
            asset_id
        )

        storage_asset_id = _text(
            storage_asset_id
        )
        actor_id = _text(
            actor_id
        )

        if not storage_asset_id:
            raise ValueError(
                "Storage authority revocation "
                "requires storageAssetId."
            )

        if not actor_id:
            raise ValueError(
                "Storage authority revocation "
                "requires actorId."
            )

        result = self._relationship_revoker(
            source_type="asset",
            source_id=_text(
                asset.get("id")
            ),
            relationship_type="mounts",
            target_type="asset",
            target_id=storage_asset_id,
            actor_id=actor_id,
            reason=(
                "Explicitly revoke blockchain storage "
                "authority from managed host"
            ),
            source=(
                "deployment-authority-management"
            ),
            execute=bool(execute),
        )

        if not isinstance(
            result,
            dict,
        ):
            raise RuntimeError(
                "Storage authority revocation did not "
                "return a result object."
            )

        return {
            **result,
            "hostAssetId": _text(
                asset.get("id")
            ),
            "storageAssetId": (
                storage_asset_id
            ),
            "executionPerformed": (
                bool(execute)
            ),
        }
