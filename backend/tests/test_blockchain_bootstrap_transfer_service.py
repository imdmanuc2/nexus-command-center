from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import MappingProxyType
from unittest.mock import Mock

from backend.executors.blockchain_deployment_executor import (
    DeploymentRequest,
)
from backend.services.blockchain_bootstrap_transfer_service import (
    BlockchainBootstrapTransferService,
    BootstrapTransferContext,
)
from backend.services.blockchain_deployment_release_service import (
    DeploymentReleaseContext,
)
from backend.transports.artifact_transfer import (
    ArtifactTransferResult,
)
from backend.transports.models import TransportTarget


class BlockchainBootstrapTransferServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)

        self.bootstrap = root / "bootstrap.tar.gz"
        self.bootstrap.write_bytes(b"bootstrap")

        self.release = DeploymentReleaseContext(
            release_id="release-test",
            runtime_version="1.0.0",
            source_revision="revision-test",
            bootstrap_artifact_id="bootstrap.tar.gz",
            bootstrap_source=self.bootstrap,
            bootstrap_sha256="a" * 64,
            runtime_artifact_id="runtime.tar.gz",
            runtime_source=root / "runtime.tar.gz",
            runtime_sha256="b" * 64,
            payload_manifest_sha256="c" * 64,
        )

        self.request = DeploymentRequest(
            provider_id="bitcoin-mainnet",
            storage_target_id="storage-main",
            target_asset_id="asset-test",
            correlation_id="corr-test",
            approved_by="approval-test",
        )

        self.target = TransportTarget(
            asset_id="asset-test",
            transport="ssh",
            host="192.0.2.10",
            username="umbrel",
            identity_file="/private/identity",
            known_hosts_file="/private/known_hosts",
        )

        self.transport = Mock()
        self.transport.transfer.return_value = (
            ArtifactTransferResult(
                artifact_id="bootstrap.tar.gz",
                remote_path=(
                    "/home/umbrel/.seymour-artifacts/"
                    "bootstrap.tar.gz"
                ),
                sha256="a" * 64,
                duration_ms=17,
                host_key_verified=True,
            )
        )

        self.service = BlockchainBootstrapTransferService(
            target=self.target,
            transport=self.transport,
            timeout_seconds=120,
        )

    def tearDown(self):
        self.temp.cleanup()

    def private_context(self):
        return MappingProxyType({
            "resolve-release": self.release,
        })

    def test_maps_reviewed_release_to_transfer_request(self):
        self.service.transfer(
            self.request,
            {},
            self.private_context(),
        )

        kwargs = self.transport.transfer.call_args.kwargs
        transfer_request = kwargs["request"]

        self.assertIs(kwargs["target"], self.target)
        self.assertEqual(
            kwargs["timeout_seconds"],
            120,
        )
        self.assertEqual(
            transfer_request.artifact_id,
            self.release.bootstrap_artifact_id,
        )
        self.assertEqual(
            transfer_request.source,
            self.release.bootstrap_source,
        )
        self.assertEqual(
            transfer_request.expected_sha256,
            self.release.bootstrap_sha256,
        )

    def test_remote_path_is_private_only(self):
        output = self.service.transfer(
            self.request,
            {},
            self.private_context(),
        )

        self.assertIsInstance(
            output.private,
            BootstrapTransferContext,
        )
        self.assertEqual(
            output.private.remote_path,
            (
                "/home/umbrel/.seymour-artifacts/"
                "bootstrap.tar.gz"
            ),
        )

        encoded = json.dumps(output.evidence)

        self.assertNotIn(
            "/home/umbrel/.seymour-artifacts",
            encoded,
        )
        self.assertNotIn(
            "remotePath",
            encoded,
        )
        self.assertNotIn(
            "remote_path",
            encoded,
        )

    def test_durable_evidence_is_sanitized(self):
        output = self.service.transfer(
            self.request,
            {},
            self.private_context(),
        )

        self.assertEqual(
            output.evidence,
            {
                "artifactId": "bootstrap.tar.gz",
                "sha256": "a" * 64,
                "durationMs": 17,
                "hostKeyVerified": True,
            },
        )

        json.dumps(
            output.evidence,
            allow_nan=False,
        )

    def test_target_details_are_not_persisted(self):
        output = self.service.transfer(
            self.request,
            {},
            self.private_context(),
        )

        encoded = json.dumps(output.evidence)

        self.assertNotIn(
            "192.0.2.10",
            encoded,
        )
        self.assertNotIn(
            "/private/identity",
            encoded,
        )
        self.assertNotIn(
            "/private/known_hosts",
            encoded,
        )

    def test_target_asset_mismatch_fails_before_transfer(self):
        request = DeploymentRequest(
            provider_id=self.request.provider_id,
            storage_target_id=self.request.storage_target_id,
            target_asset_id="asset-other",
            correlation_id=self.request.correlation_id,
            approved_by=self.request.approved_by,
        )

        with self.assertRaisesRegex(
            ValueError,
            "does not match deployment target",
        ):
            self.service.transfer(
                request,
                {},
                self.private_context(),
            )

        self.transport.transfer.assert_not_called()

    def test_missing_release_context_fails_before_transfer(self):
        with self.assertRaisesRegex(
            ValueError,
            "reviewed release context",
        ):
            self.service.transfer(
                self.request,
                {},
                MappingProxyType({}),
            )

        self.transport.transfer.assert_not_called()

    def test_transfer_identity_mismatch_fails_closed(self):
        self.transport.transfer.return_value = (
            ArtifactTransferResult(
                artifact_id="wrong.tar.gz",
                remote_path="/private/wrong",
                sha256="a" * 64,
                duration_ms=1,
                host_key_verified=True,
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "identity mismatch",
        ):
            self.service.transfer(
                self.request,
                {},
                self.private_context(),
            )

    def test_transfer_hash_mismatch_fails_closed(self):
        self.transport.transfer.return_value = (
            ArtifactTransferResult(
                artifact_id="bootstrap.tar.gz",
                remote_path="/private/bootstrap",
                sha256="f" * 64,
                duration_ms=1,
                host_key_verified=True,
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "SHA-256 mismatch",
        ):
            self.service.transfer(
                self.request,
                {},
                self.private_context(),
            )

    def test_missing_remote_path_fails_closed(self):
        self.transport.transfer.return_value = (
            ArtifactTransferResult(
                artifact_id="bootstrap.tar.gz",
                remote_path="",
                sha256="a" * 64,
                duration_ms=1,
                host_key_verified=True,
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "remote path is missing",
        ):
            self.service.transfer(
                self.request,
                {},
                self.private_context(),
            )

    def test_unverified_host_key_fails_closed(self):
        self.transport.transfer.return_value = (
            ArtifactTransferResult(
                artifact_id="bootstrap.tar.gz",
                remote_path="/private/bootstrap",
                sha256="a" * 64,
                duration_ms=1,
                host_key_verified=False,
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "did not verify target host key",
        ):
            self.service.transfer(
                self.request,
                {},
                self.private_context(),
            )

    def test_timeout_must_be_positive(self):
        with self.assertRaisesRegex(
            ValueError,
            "timeout must be positive",
        ):
            BlockchainBootstrapTransferService(
                target=self.target,
                transport=self.transport,
                timeout_seconds=0,
            )


if __name__ == "__main__":
    unittest.main()
