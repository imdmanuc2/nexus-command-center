from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.executors.blockchain_deployment_executor import (
    DeploymentRequest,
)
from backend.services.blockchain_deployment_target_service import (
    BlockchainDeploymentTargetService,
    DeploymentTargetContext,
)
from backend.services.blockchain_deployment_storage_service import (
    BlockchainDeploymentStorageService,
    DeploymentStorageContext,
)
from backend.services.blockchain_target_platform import (
    TargetPlatformProfile,
)
from backend.transports.models import (
    TransportTarget,
)
from backend.transports.target_prerequisites import (
    SshTargetPrerequisiteTransport,
    TargetPrerequisiteResult,
)


@dataclass(frozen=True, slots=True)
class BlockchainDeploymentPreflightContext:
    target: TransportTarget
    profile: TargetPlatformProfile
    storage: DeploymentStorageContext
    prerequisites: TargetPrerequisiteResult


@dataclass(frozen=True, slots=True)
class BlockchainDeploymentPreflightResult:
    context: BlockchainDeploymentPreflightContext
    evidence: dict[str, Any]


class BlockchainDeploymentPreflightService:
    """
    Resolve and verify the deployment target before any durable
    blockchain deployment step begins.

    This service deliberately does not add a BlockchainDeploymentExecutor
    step. Target resolution and prerequisite checks are pre-execution
    safety gates, not deployment mutations.

    Transport details, filesystem paths, SSH trust material, and the
    platform profile remain private. Only sanitized target/platform and
    prerequisite identities are returned as evidence.
    """

    def __init__(
        self,
        *,
        target_service: BlockchainDeploymentTargetService | None = None,
        storage_service: BlockchainDeploymentStorageService | None = None,
        prerequisite_transport: (
            SshTargetPrerequisiteTransport | None
        ) = None,
        timeout_seconds: int = 30,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError(
                "Deployment preflight timeout must be positive"
            )

        self._target_service = (
            target_service
            or BlockchainDeploymentTargetService()
        )
        self._storage_service = (
            storage_service
            or BlockchainDeploymentStorageService()
        )
        self._prerequisite_transport = (
            prerequisite_transport
            or SshTargetPrerequisiteTransport()
        )
        self._timeout_seconds = timeout_seconds

    def verify(
        self,
        request: DeploymentRequest,
    ) -> BlockchainDeploymentPreflightResult:
        target_output = self._target_service.resolve(
            request
        )

        target_context = target_output.private

        if not isinstance(
            target_context,
            DeploymentTargetContext,
        ):
            raise ValueError(
                "Deployment target service returned invalid private context"
            )

        target = target_context.target
        profile = target_context.profile

        if target.asset_id != request.target_asset_id:
            raise ValueError(
                "Deployment preflight target identity mismatch"
            )

        if target.transport != "ssh":
            raise ValueError(
                "Deployment preflight requires SSH target"
            )

        if profile.platform_id != str(
            target_output.evidence.get(
                "deploymentPlatformId"
            )
            or ""
        ).strip():
            raise ValueError(
                "Deployment preflight platform identity mismatch"
            )

        storage = self._storage_service.resolve(
            request
        )

        if not isinstance(
            storage,
            DeploymentStorageContext,
        ):
            raise ValueError(
                "Deployment storage service returned invalid context"
            )

        if storage.target_asset_id != request.target_asset_id:
            raise ValueError(
                "Deployment storage target-host identity mismatch"
            )

        if storage.storage_asset_id != request.storage_target_id:
            raise ValueError(
                "Deployment storage identity mismatch"
            )

        prerequisites = (
            self._prerequisite_transport.verify(
                target=target,
                profile=profile,
                timeout_seconds=self._timeout_seconds,
            )
        )

        if not isinstance(
            prerequisites,
            TargetPrerequisiteResult,
        ):
            raise ValueError(
                "Deployment prerequisite verification returned invalid result"
            )

        if prerequisites.platform_id != profile.platform_id:
            raise ValueError(
                "Deployment prerequisite platform identity mismatch"
            )

        if prerequisites.host_key_verified is not True:
            raise ValueError(
                "Deployment prerequisite host key was not verified"
            )

        checks = tuple(prerequisites.checks)

        if not checks:
            raise ValueError(
                "Deployment prerequisite checks are missing"
            )

        evidence = {
            "targetAssetId": request.target_asset_id,
            "transport": "ssh",
            "deploymentPlatformId": profile.platform_id,
            "storageTargetId": storage.storage_asset_id,
            "storageAssetType": storage.storage_asset_type,
            "prerequisites": {
                "checks": list(checks),
                "pythonVersion": (
                    prerequisites.python_version
                ),
                "tarVersion": (
                    prerequisites.tar_version
                ),
                "durationMs": (
                    prerequisites.duration_ms
                ),
                "hostKeyVerified": True,
            },
        }

        context = BlockchainDeploymentPreflightContext(
            target=target,
            profile=profile,
            storage=storage,
            prerequisites=prerequisites,
        )

        return BlockchainDeploymentPreflightResult(
            context=context,
            evidence=evidence,
        )
