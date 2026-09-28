from __future__ import annotations

import unittest

from backend.executors.blockchain_deployment_executor import (
    DeploymentRequest,
)
from backend.services.blockchain_bootstrap_invocation_service import (
    BootstrapInvocationContext,
)
from backend.services.blockchain_deployment_release_service import (
    DeploymentReleaseContext,
)
from backend.services.blockchain_runtime_verification_service import (
    BlockchainRuntimeVerificationService,
    RuntimeVerificationContext,
)
from backend.transports.models import (
    TransportTarget,
)
from backend.transports.runtime_verification import (
    RuntimeVerificationResult,
)


PAYLOAD_SHA = "a" * 64


class FakeRuntimeVerificationTransport:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def verify(
        self,
        *,
        target,
        request,
        timeout_seconds,
    ):
        self.calls.append(
            {
                "target": target,
                "request": request,
                "timeout": timeout_seconds,
            }
        )

        return self.result


def release_context():
    return DeploymentReleaseContext(
        release_id="release-1",
        runtime_version="1.0.0",
        source_revision="revision-1",
        bootstrap_artifact_id="bootstrap.tar.gz",
        bootstrap_source="/private/bootstrap.tar.gz",
        bootstrap_sha256="b" * 64,
        runtime_artifact_id="runtime.tar.gz",
        runtime_source="/private/runtime.tar.gz",
        runtime_sha256="c" * 64,
        payload_manifest_sha256=PAYLOAD_SHA,
    )


def bootstrap_context():
    return BootstrapInvocationContext(
        runtime_version="1.0.0",
        source_revision="revision-1",
        runtime_sha256="c" * 64,
        payload_manifest_sha256=PAYLOAD_SHA,
    )


def good_result():
    return RuntimeVerificationResult(
        runtime_version="1.0.0",
        source_revision="revision-1",
        payload_manifest_sha256=PAYLOAD_SHA,
        executable_present=True,
        duration_ms=7,
        host_key_verified=True,
    )


class BlockchainRuntimeVerificationServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.target = TransportTarget(
            asset_id="asset-1",
            transport="ssh",
            host="192.0.2.10",
            port=22,
            username="umbrel",
            identity_file="/private/key",
            known_hosts_file="/private/known_hosts",
        )

        self.request = DeploymentRequest(
            provider_id="bitcoin-mainnet",
            storage_target_id="storage-main",
            target_asset_id="asset-1",
            correlation_id="corr-1",
            approved_by="operator",
        )

    def private(self):
        return {
            "resolve-release": release_context(),
            "invoke-bootstrap": bootstrap_context(),
        }

    def service(self, result=None):
        fake = FakeRuntimeVerificationTransport(
            result or good_result()
        )

        service = BlockchainRuntimeVerificationService(
            target=self.target,
            transport=fake,
            timeout_seconds=30,
        )

        return service, fake

    def test_maps_trusted_context_to_typed_verification(self):
        service, fake = self.service()

        output = service.execute(
            request=self.request,
            private=self.private(),
        )

        self.assertEqual(
            len(fake.calls),
            1,
        )

        typed = fake.calls[0]["request"]

        self.assertEqual(
            typed.runtime_version,
            "1.0.0",
        )
        self.assertEqual(
            typed.source_revision,
            "revision-1",
        )
        self.assertEqual(
            typed.payload_manifest_sha256,
            PAYLOAD_SHA,
        )

    def test_target_asset_mismatch_fails_before_transport(self):
        request = DeploymentRequest(
            provider_id="bitcoin-mainnet",
            storage_target_id="storage-main",
            target_asset_id="asset-2",
            correlation_id="corr-1",
            approved_by="operator",
        )

        service, fake = self.service()

        with self.assertRaisesRegex(
            ValueError,
            "target does not match",
        ):
            service.execute(
                request=request,
                private=self.private(),
            )

        self.assertEqual(
            fake.calls,
            [],
        )

    def test_missing_release_context_fails_closed(self):
        service, fake = self.service()

        with self.assertRaisesRegex(
            ValueError,
            "resolve-release",
        ):
            service.execute(
                request=self.request,
                private={
                    "invoke-bootstrap": bootstrap_context(),
                },
            )

        self.assertEqual(
            fake.calls,
            [],
        )

    def test_missing_bootstrap_context_fails_closed(self):
        service, fake = self.service()

        with self.assertRaisesRegex(
            ValueError,
            "invoke-bootstrap",
        ):
            service.execute(
                request=self.request,
                private={
                    "resolve-release": release_context(),
                },
            )

        self.assertEqual(
            fake.calls,
            [],
        )

    def test_bootstrap_version_mismatch_fails_closed(self):
        private = self.private()

        private["invoke-bootstrap"] = (
            BootstrapInvocationContext(
                runtime_version="2.0.0",
                source_revision="revision-1",
                runtime_sha256="c" * 64,
                payload_manifest_sha256=PAYLOAD_SHA,
            )
        )

        service, fake = self.service()

        with self.assertRaisesRegex(
            ValueError,
            "runtime version",
        ):
            service.execute(
                request=self.request,
                private=private,
            )

        self.assertEqual(
            fake.calls,
            [],
        )

    def test_bootstrap_revision_mismatch_fails_closed(self):
        private = self.private()

        private["invoke-bootstrap"] = (
            BootstrapInvocationContext(
                runtime_version="1.0.0",
                source_revision="wrong",
                runtime_sha256="c" * 64,
                payload_manifest_sha256=PAYLOAD_SHA,
            )
        )

        service, fake = self.service()

        with self.assertRaisesRegex(
            ValueError,
            "source revision",
        ):
            service.execute(
                request=self.request,
                private=private,
            )

        self.assertEqual(
            fake.calls,
            [],
        )

    def test_bootstrap_payload_mismatch_fails_closed(self):
        private = self.private()

        private["invoke-bootstrap"] = (
            BootstrapInvocationContext(
                runtime_version="1.0.0",
                source_revision="revision-1",
                runtime_sha256="c" * 64,
                payload_manifest_sha256="d" * 64,
            )
        )

        service, fake = self.service()

        with self.assertRaisesRegex(
            ValueError,
            "payload manifest",
        ):
            service.execute(
                request=self.request,
                private=private,
            )

        self.assertEqual(
            fake.calls,
            [],
        )

    def test_result_version_mismatch_fails_closed(self):
        bad = good_result()

        result = RuntimeVerificationResult(
            runtime_version="2.0.0",
            source_revision=bad.source_revision,
            payload_manifest_sha256=(
                bad.payload_manifest_sha256
            ),
            executable_present=True,
            duration_ms=7,
            host_key_verified=True,
        )

        service, _ = self.service(result)

        with self.assertRaisesRegex(
            ValueError,
            "Verified runtime version",
        ):
            service.execute(
                request=self.request,
                private=self.private(),
            )

    def test_result_revision_mismatch_fails_closed(self):
        bad = good_result()

        result = RuntimeVerificationResult(
            runtime_version=bad.runtime_version,
            source_revision="wrong",
            payload_manifest_sha256=(
                bad.payload_manifest_sha256
            ),
            executable_present=True,
            duration_ms=7,
            host_key_verified=True,
        )

        service, _ = self.service(result)

        with self.assertRaisesRegex(
            ValueError,
            "Verified source revision",
        ):
            service.execute(
                request=self.request,
                private=self.private(),
            )

    def test_result_payload_mismatch_fails_closed(self):
        bad = good_result()

        result = RuntimeVerificationResult(
            runtime_version=bad.runtime_version,
            source_revision=bad.source_revision,
            payload_manifest_sha256="d" * 64,
            executable_present=True,
            duration_ms=7,
            host_key_verified=True,
        )

        service, _ = self.service(result)

        with self.assertRaisesRegex(
            ValueError,
            "Verified payload manifest",
        ):
            service.execute(
                request=self.request,
                private=self.private(),
            )

    def test_missing_executable_fails_closed(self):
        result = RuntimeVerificationResult(
            runtime_version="1.0.0",
            source_revision="revision-1",
            payload_manifest_sha256=PAYLOAD_SHA,
            executable_present=False,
            duration_ms=7,
            host_key_verified=True,
        )

        service, _ = self.service(result)

        with self.assertRaisesRegex(
            ValueError,
            "executable is unavailable",
        ):
            service.execute(
                request=self.request,
                private=self.private(),
            )

    def test_unverified_host_key_fails_closed(self):
        result = RuntimeVerificationResult(
            runtime_version="1.0.0",
            source_revision="revision-1",
            payload_manifest_sha256=PAYLOAD_SHA,
            executable_present=True,
            duration_ms=7,
            host_key_verified=False,
        )

        service, _ = self.service(result)

        with self.assertRaisesRegex(
            ValueError,
            "did not verify host key",
        ):
            service.execute(
                request=self.request,
                private=self.private(),
            )

    def test_durable_evidence_is_sanitized(self):
        service, _ = self.service()

        output = service.execute(
            request=self.request,
            private=self.private(),
        )

        self.assertEqual(
            output.evidence,
            {
                "runtimeVersion": "1.0.0",
                "sourceRevision": "revision-1",
                "payloadManifestSha256": PAYLOAD_SHA,
                "executablePresent": True,
                "durationMs": 7,
                "hostKeyVerified": True,
            },
        )

        encoded = repr(output.evidence)

        self.assertNotIn(
            "192.0.2.10",
            encoded,
        )
        self.assertNotIn(
            "/home/umbrel",
            encoded,
        )
        self.assertNotIn(
            "/private/",
            encoded,
        )

    def test_private_context_is_typed(self):
        service, _ = self.service()

        output = service.execute(
            request=self.request,
            private=self.private(),
        )

        self.assertIsInstance(
            output.private,
            RuntimeVerificationContext,
        )

        self.assertEqual(
            output.private.runtime_version,
            "1.0.0",
        )

    def test_public_request_does_not_supply_verification_identity(self):
        fields = set(
            self.request.__dataclass_fields__
        )

        forbidden = {
            "runtime_version",
            "source_revision",
            "runtime_sha256",
            "payload_manifest_sha256",
            "runtime_root",
            "platform_id",
        }

        self.assertTrue(
            forbidden.isdisjoint(fields)
        )


if __name__ == "__main__":
    unittest.main()
