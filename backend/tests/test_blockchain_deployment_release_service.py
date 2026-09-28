from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.executors.blockchain_deployment_executor import (
    DeploymentRequest,
)
from backend.services.blockchain_deployment_release_service import (
    BlockchainDeploymentReleaseService,
)
from backend.services.blockchain_release_resolver import (
    BlockchainRelease,
    ReviewedArtifact,
)


class FakeResolver:
    def __init__(self, release):
        self.release = release
        self.calls = 0

    def resolve(self):
        self.calls += 1
        return self.release


class BlockchainDeploymentReleaseServiceTests(unittest.TestCase):
    def request(self):
        return DeploymentRequest(
            provider_id="bitcoin-mainnet",
            storage_target_id="storage-main",
            target_asset_id="asset-test",
            correlation_id="corr-test",
            approved_by="approval-test",
        )

    def release(self, root: Path):
        bootstrap = root / "bootstrap.tar.gz"
        runtime = root / "runtime.tar.gz"

        return BlockchainRelease(
            release_id="release-test",
            runtime_version="1.0.0",
            source_revision="revision-test",
            bootstrap=ReviewedArtifact(
                artifact_id="bootstrap.tar.gz",
                source=bootstrap,
                sha256="a" * 64,
            ),
            runtime=ReviewedArtifact(
                artifact_id="runtime.tar.gz",
                source=runtime,
                sha256="b" * 64,
            ),
            payload_manifest_sha256="c" * 64,
        )

    def test_resolves_internal_paths_for_later_steps(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            resolver = FakeResolver(self.release(root))
            service = BlockchainDeploymentReleaseService(
                resolver=resolver
            )

            context = service.resolve(self.request())

            self.assertEqual(resolver.calls, 1)
            self.assertEqual(
                context.bootstrap_source,
                root / "bootstrap.tar.gz",
            )
            self.assertEqual(
                context.runtime_source,
                root / "runtime.tar.gz",
            )

    def test_evidence_omits_internal_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            service = BlockchainDeploymentReleaseService(
                resolver=FakeResolver(self.release(root))
            )

            evidence = service.resolve_evidence(
                self.request()
            )
            encoded = json.dumps(evidence)

            self.assertNotIn(str(root), encoded)
            self.assertNotIn(
                "source",
                evidence["bootstrap"],
            )
            self.assertNotIn(
                "source",
                evidence["runtime"],
            )
            self.assertEqual(
                evidence["sourceRevision"],
                "revision-test",
            )

    def test_public_request_does_not_select_release_hashes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release = self.release(root)
            resolver = FakeResolver(release)
            service = BlockchainDeploymentReleaseService(
                resolver=resolver
            )

            first = service.resolve_evidence(
                self.request()
            )

            other = DeploymentRequest(
                provider_id="monero-mainnet",
                storage_target_id="other-storage",
                target_asset_id="other-host",
                correlation_id="other-correlation",
                approved_by="other-approval",
            )

            second = service.resolve_evidence(other)

            self.assertEqual(
                first["bootstrap"]["sha256"],
                second["bootstrap"]["sha256"],
            )
            self.assertEqual(
                first["runtime"]["sha256"],
                second["runtime"]["sha256"],
            )
            self.assertEqual(
                first["releaseId"],
                second["releaseId"],
            )

    def test_evidence_shape_matches_resolver_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release = self.release(root)
            service = BlockchainDeploymentReleaseService(
                resolver=FakeResolver(release)
            )

            evidence = service.resolve_evidence(
                self.request()
            )

            self.assertEqual(
                evidence,
                release.evidence(),
            )

    def test_resolve_step_separates_private_context_from_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release = self.release(root)
            service = BlockchainDeploymentReleaseService(
                resolver=FakeResolver(release)
            )

            output = service.resolve_step(
                self.request()
            )

            self.assertEqual(
                output.evidence,
                release.evidence(),
            )

            self.assertEqual(
                output.private.bootstrap_source,
                root / "bootstrap.tar.gz",
            )

            self.assertEqual(
                output.private.runtime_source,
                root / "runtime.tar.gz",
            )

            encoded = json.dumps(output.evidence)

            self.assertNotIn(str(root), encoded)


if __name__ == "__main__":
    unittest.main()
