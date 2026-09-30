from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from backend.db.repositories import asset_repository


class BlockchainRuntimeAuthorityProjectionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RuntimeAuthorityProjection:
    runtime_asset_id: str
    provider_id: str
    host_asset_id: str
    storage_asset_id: str


def _text(value: Any) -> str:
    return str(value or "").strip()


class BlockchainRuntimeAuthorityProjectionService:
    """
    Project authority from a verified successful blockchain deployment onto
    the corresponding registered runtime CMDB asset.

    Authority:
      providerId     <- DeploymentResult.provider_id
      hostAssetId    <- DeploymentResult.target_asset_id
      storageAssetId <- DeploymentResult.storage_target_id

    Runtime identity remains registration-owned. No IP inference, endpoint
    inference, mount-count guessing, or BM physical-local identity is used.
    """

    def __init__(
        self,
        *,
        runtime_finder: Callable[
            [str],
            list[dict[str, Any]],
        ] | None = None,
        metadata_merger: Callable[
            [str, dict[str, Any]],
            dict[str, Any],
        ] | None = None,
    ) -> None:
        self._runtime_finder = (
            runtime_finder
            or asset_repository.find_registered_blockchain_runtimes
        )
        self._metadata_merger = (
            metadata_merger
            or asset_repository.merge_asset_metadata
        )

    def project(
        self,
        *,
        provider_id: str,
        target_asset_id: str,
        storage_target_id: str,
    ) -> RuntimeAuthorityProjection:
        provider_id = _text(provider_id)
        target_asset_id = _text(target_asset_id)
        storage_target_id = _text(storage_target_id)

        if not provider_id:
            raise BlockchainRuntimeAuthorityProjectionError(
                "provider_id is required"
            )

        if not target_asset_id:
            raise BlockchainRuntimeAuthorityProjectionError(
                "target_asset_id is required"
            )

        if not storage_target_id:
            raise BlockchainRuntimeAuthorityProjectionError(
                "storage_target_id is required"
            )

        matches = self._runtime_finder(provider_id)

        if len(matches) != 1:
            ids = sorted(
                _text(
                    match.get("assetId")
                    or match.get("id")
                )
                for match in matches
                if isinstance(match, dict)
            )

            raise BlockchainRuntimeAuthorityProjectionError(
                "Expected exactly one registered blockchain runtime "
                f"for providerId={provider_id}; matches="
                f"{[value for value in ids if value]}"
            )

        runtime = matches[0]

        if not isinstance(runtime, dict):
            raise BlockchainRuntimeAuthorityProjectionError(
                "Registered runtime result is invalid"
            )

        runtime_id = _text(
            runtime.get("assetId")
            or runtime.get("id")
        )

        if not runtime_id:
            raise BlockchainRuntimeAuthorityProjectionError(
                "Registered runtime has no asset ID"
            )

        metadata = runtime.get("metadata")

        if not isinstance(metadata, dict):
            raise BlockchainRuntimeAuthorityProjectionError(
                "Registered runtime has no metadata"
            )

        if _text(metadata.get("providerId")) != provider_id:
            raise BlockchainRuntimeAuthorityProjectionError(
                "Registered runtime provider identity mismatch"
            )

        if not _text(metadata.get("appId")):
            raise BlockchainRuntimeAuthorityProjectionError(
                "Registered runtime has no app identity"
            )

        for key, expected in (
            ("hostAssetId", target_asset_id),
            ("storageAssetId", storage_target_id),
        ):
            existing = _text(metadata.get(key))

            if existing and existing != expected:
                raise BlockchainRuntimeAuthorityProjectionError(
                    f"Existing {key} conflicts with verified "
                    "deployment authority"
                )

        patch = {
            "providerId": provider_id,
            "hostAssetId": target_asset_id,
            "storageAssetId": storage_target_id,
        }

        if all(
            _text(metadata.get(key)) == expected
            for key, expected in patch.items()
        ):
            return RuntimeAuthorityProjection(
                runtime_asset_id=runtime_id,
                provider_id=provider_id,
                host_asset_id=target_asset_id,
                storage_asset_id=storage_target_id,
            )

        updated = self._metadata_merger(
            runtime_id,
            patch,
        )

        confirmed = updated.get("metadata")

        if not isinstance(confirmed, dict):
            raise BlockchainRuntimeAuthorityProjectionError(
                "Metadata projection returned no confirmation"
            )

        for key, expected in patch.items():
            if _text(confirmed.get(key)) != expected:
                raise BlockchainRuntimeAuthorityProjectionError(
                    f"Authority projection verification failed for {key}"
                )

        return RuntimeAuthorityProjection(
            runtime_asset_id=runtime_id,
            provider_id=provider_id,
            host_asset_id=target_asset_id,
            storage_asset_id=storage_target_id,
        )
