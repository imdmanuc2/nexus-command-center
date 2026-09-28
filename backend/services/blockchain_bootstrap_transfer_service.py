from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from backend.executors.blockchain_deployment_executor import (
    DeploymentRequest,
    DeploymentStepOutput,
)
from backend.services.blockchain_deployment_release_service import (
    DeploymentReleaseContext,
)
from backend.transports.artifact_transfer import (
    ArtifactTransferRequest,
    ArtifactTransferResult,
    SshArtifactTransport,
)
from backend.transports.models import TransportTarget


@dataclass(frozen=True, slots=True)
class BootstrapTransferContext:
    artifact_id: str
    remote_path: str
    sha256: str


class BlockchainBootstrapTransferService:
    """
    Transfer the reviewed bootstrap artifact to an already-resolved target.

    Release filesystem paths, TransportTarget details, and the derived
    remote staging path remain private orchestration state.

    Durable evidence contains only reviewed artifact identity/hash and
    transfer verification metadata.
    """

    def __init__(
        self,
        *,
        target: TransportTarget,
        transport: SshArtifactTransport | None = None,
        timeout_seconds: int = 120,
    ) -> None:
        self._target = target
        self._transport = transport or SshArtifactTransport()
        self._timeout_seconds = int(timeout_seconds)

        if self._timeout_seconds <= 0:
            raise ValueError(
                "Bootstrap transfer timeout must be positive"
            )

    @staticmethod
    def _release(
        private_context: Mapping[str, Any],
    ) -> DeploymentReleaseContext:
        release = private_context.get("resolve-release")

        if not isinstance(release, DeploymentReleaseContext):
            raise ValueError(
                "Bootstrap transfer requires reviewed release context"
            )

        return release

    def transfer(
        self,
        request: DeploymentRequest,
        evidence_context: dict[str, Any],
        private_context: Mapping[str, Any],
    ) -> DeploymentStepOutput:
        del evidence_context

        if self._target.asset_id != request.target_asset_id:
            raise ValueError(
                "Resolved transfer target does not match deployment target"
            )

        release = self._release(private_context)

        transfer_request = ArtifactTransferRequest(
            artifact_id=release.bootstrap_artifact_id,
            source=release.bootstrap_source,
            expected_sha256=release.bootstrap_sha256,
        )

        result = self._transport.transfer(
            target=self._target,
            request=transfer_request,
            timeout_seconds=self._timeout_seconds,
        )

        self._validate_result(
            release=release,
            result=result,
        )

        private = BootstrapTransferContext(
            artifact_id=result.artifact_id,
            remote_path=result.remote_path,
            sha256=result.sha256,
        )

        return DeploymentStepOutput(
            evidence={
                "artifactId": result.artifact_id,
                "sha256": result.sha256,
                "durationMs": result.duration_ms,
                "hostKeyVerified": result.host_key_verified,
            },
            private=private,
        )

    @staticmethod
    def _validate_result(
        *,
        release: DeploymentReleaseContext,
        result: ArtifactTransferResult,
    ) -> None:
        if result.artifact_id != release.bootstrap_artifact_id:
            raise ValueError(
                "Transferred bootstrap artifact identity mismatch"
            )

        if result.sha256 != release.bootstrap_sha256:
            raise ValueError(
                "Transferred bootstrap artifact SHA-256 mismatch"
            )

        if not result.remote_path:
            raise ValueError(
                "Transferred bootstrap remote path is missing"
            )

        if not result.host_key_verified:
            raise ValueError(
                "Bootstrap transfer did not verify target host key"
            )
