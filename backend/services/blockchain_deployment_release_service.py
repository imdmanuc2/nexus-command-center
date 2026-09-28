from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.executors.blockchain_deployment_executor import (
    DeploymentRequest,
    DeploymentStepOutput,
)
from backend.services.blockchain_release_resolver import (
    BlockchainRelease,
    BlockchainReleaseResolver,
)


@dataclass(frozen=True, slots=True)
class DeploymentReleaseContext:
    release_id: str
    runtime_version: str
    source_revision: str
    bootstrap_artifact_id: str
    bootstrap_source: Path
    bootstrap_sha256: str
    runtime_artifact_id: str
    runtime_source: Path
    runtime_sha256: str
    payload_manifest_sha256: str

    def evidence(self) -> dict[str, Any]:
        return {
            "releaseId": self.release_id,
            "runtimeVersion": self.runtime_version,
            "sourceRevision": self.source_revision,
            "bootstrap": {
                "artifactId": self.bootstrap_artifact_id,
                "sha256": self.bootstrap_sha256,
            },
            "runtime": {
                "artifactId": self.runtime_artifact_id,
                "sha256": self.runtime_sha256,
                "payloadManifestSha256": (
                    self.payload_manifest_sha256
                ),
            },
        }


class BlockchainDeploymentReleaseService:
    """
    Resolve the reviewed Nexus-owned blockchain release.

    Filesystem paths remain internal to DeploymentReleaseContext and
    are deliberately omitted from persisted deployment evidence.
    """

    def __init__(
        self,
        resolver: BlockchainReleaseResolver | None = None,
    ) -> None:
        self._resolver = resolver or BlockchainReleaseResolver()

    @staticmethod
    def _context(
        release: BlockchainRelease,
    ) -> DeploymentReleaseContext:
        return DeploymentReleaseContext(
            release_id=release.release_id,
            runtime_version=release.runtime_version,
            source_revision=release.source_revision,
            bootstrap_artifact_id=release.bootstrap.artifact_id,
            bootstrap_source=release.bootstrap.source,
            bootstrap_sha256=release.bootstrap.sha256,
            runtime_artifact_id=release.runtime.artifact_id,
            runtime_source=release.runtime.source,
            runtime_sha256=release.runtime.sha256,
            payload_manifest_sha256=(
                release.payload_manifest_sha256
            ),
        )

    def resolve(
        self,
        request: DeploymentRequest,
    ) -> DeploymentReleaseContext:
        # The reviewed release is Nexus-owned and independent of
        # public provider/storage parameters. Those parameters select
        # the eventual target installation, not artifact trust.
        del request
        return self._context(self._resolver.resolve())

    def resolve_evidence(
        self,
        request: DeploymentRequest,
    ) -> dict[str, Any]:
        return self.resolve(request).evidence()

    def resolve_step(
        self,
        request: DeploymentRequest,
    ) -> DeploymentStepOutput:
        context = self.resolve(request)

        return DeploymentStepOutput(
            evidence=context.evidence(),
            private=context,
        )
