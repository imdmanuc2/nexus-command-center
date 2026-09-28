from __future__ import annotations

import unittest

from backend.executors.blockchain_deployment_executor import (
    DeploymentRequest,
)
from backend.services.blockchain_installer_invocation_service import (
    BlockchainInstallerInvocationContext,
    BlockchainInstallerInvocationService,
)
from backend.services.blockchain_runtime_verification_service import (
    RuntimeVerificationContext,
)
from backend.transports.blockchain_installer_invocation import (
    BlockchainInstallerInvocationResult,
)
from backend.transports.models import TransportTarget


class FakeInstallerTransport:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def invoke(
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


def verified_runtime():
    return RuntimeVerificationContext(
        runtime_version="1.0.0",
        source_revision="revision-1",
        payload_manifest_sha256="a" * 64,
    )


def good_result():
    return BlockchainInstallerInvocationResult(
        provider_id="bitcoin-mainnet",
        storage_target_id="storage-main",
        success=True,
        duration_ms=11,
        exit_code=0,
        host_key_verified=True,
        result={
            "operationId": "op-test-install",
            "status": "succeeded",
            "result": {},
            "verification": {
                "verified": True,
                "evidence": {},
                "error": None,
            },
            "error": None,
        },
    )


class BlockchainInstallerInvocationServiceTests(
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

    def service(self, result=None):
        fake = FakeInstallerTransport(
            result or good_result()
        )

        service = BlockchainInstallerInvocationService(
            target=self.target,
            transport=fake,
            timeout_seconds=900,
        )

        return service, fake

    def private(self):
        return {
            "verify-runtime": verified_runtime(),
        }

    def test_maps_approved_request_to_typed_invocation(self):
        service, fake = self.service()

        output = service.execute(
            request=self.request,
            private=self.private(),
        )

        self.assertEqual(len(fake.calls), 1)

        typed = fake.calls[0]["request"]

        self.assertEqual(
            typed.provider_id,
            "bitcoin-mainnet",
        )
        self.assertEqual(
            typed.storage_target_id,
            "storage-main",
        )
        self.assertEqual(
            fake.calls[0]["timeout"],
            900,
        )

        self.assertTrue(output.evidence["success"])

    def test_requires_verify_runtime_private_state(self):
        service, fake = self.service()

        with self.assertRaisesRegex(
            ValueError,
            "verify-runtime",
        ):
            service.execute(
                request=self.request,
                private={},
            )

        self.assertEqual(fake.calls, [])

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

        self.assertEqual(fake.calls, [])

    def test_non_ssh_target_fails_before_transport(self):
        target = TransportTarget(
            asset_id="asset-1",
            transport="local",
        )

        fake = FakeInstallerTransport(
            good_result()
        )

        service = BlockchainInstallerInvocationService(
            target=target,
            transport=fake,
        )

        with self.assertRaisesRegex(
            ValueError,
            "must use SSH",
        ):
            service.execute(
                request=self.request,
                private=self.private(),
            )

        self.assertEqual(fake.calls, [])

    def test_result_provider_mismatch_fails_closed(self):
        result = good_result()

        bad = BlockchainInstallerInvocationResult(
            provider_id="wrong-provider",
            storage_target_id=result.storage_target_id,
            success=True,
            duration_ms=11,
            exit_code=0,
            host_key_verified=True,
            result=result.result,
        )

        service, _ = self.service(bad)

        with self.assertRaisesRegex(
            ValueError,
            "result provider",
        ):
            service.execute(
                request=self.request,
                private=self.private(),
            )

    def test_result_storage_mismatch_fails_closed(self):
        result = good_result()

        bad = BlockchainInstallerInvocationResult(
            provider_id=result.provider_id,
            storage_target_id="wrong-storage",
            success=True,
            duration_ms=11,
            exit_code=0,
            host_key_verified=True,
            result=result.result,
        )

        service, _ = self.service(bad)

        with self.assertRaisesRegex(
            ValueError,
            "result storage target",
        ):
            service.execute(
                request=self.request,
                private=self.private(),
            )

    def test_unsuccessful_result_fails_closed(self):
        result = good_result()

        bad = BlockchainInstallerInvocationResult(
            provider_id=result.provider_id,
            storage_target_id=result.storage_target_id,
            success=False,
            duration_ms=11,
            exit_code=0,
            host_key_verified=True,
            result=result.result,
        )

        service, _ = self.service(bad)

        with self.assertRaisesRegex(
            ValueError,
            "did not report success",
        ):
            service.execute(
                request=self.request,
                private=self.private(),
            )

    def test_nonzero_exit_fails_closed(self):
        result = good_result()

        bad = BlockchainInstallerInvocationResult(
            provider_id=result.provider_id,
            storage_target_id=result.storage_target_id,
            success=True,
            duration_ms=11,
            exit_code=1,
            host_key_verified=True,
            result=result.result,
        )

        service, _ = self.service(bad)

        with self.assertRaisesRegex(
            ValueError,
            "nonzero exit code",
        ):
            service.execute(
                request=self.request,
                private=self.private(),
            )

    def test_unverified_host_key_fails_closed(self):
        result = good_result()

        bad = BlockchainInstallerInvocationResult(
            provider_id=result.provider_id,
            storage_target_id=result.storage_target_id,
            success=True,
            duration_ms=11,
            exit_code=0,
            host_key_verified=False,
            result=result.result,
        )

        service, _ = self.service(bad)

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
                "providerId": "bitcoin-mainnet",
                "storageTargetId": "storage-main",
                "success": True,
                "durationMs": 11,
                "exitCode": 0,
                "hostKeyVerified": True,
            },
        )

        encoded = repr(output.evidence)

        self.assertNotIn("192.0.2.10", encoded)
        self.assertNotIn("/home/umbrel", encoded)
        self.assertNotIn("/private/", encoded)

    def test_private_context_is_typed(self):
        service, _ = self.service()

        output = service.execute(
            request=self.request,
            private=self.private(),
        )

        self.assertIsInstance(
            output.private,
            BlockchainInstallerInvocationContext,
        )

        self.assertEqual(
            output.private.operation_id,
            "op-test-install",
        )

        self.assertEqual(
            output.private.provider_id,
            "bitcoin-mainnet",
        )
        self.assertEqual(
            output.private.storage_target_id,
            "storage-main",
        )
        self.assertTrue(
            output.private.success
        )

    def test_service_owns_no_path_or_command_surface(self):
        fields = set(
            self.request.__dataclass_fields__
        )

        forbidden = {
            "command",
            "argv",
            "shell",
            "executable",
            "runtime_root",
            "remote_path",
            "platform_id",
            "runtime_version",
            "source_revision",
            "payload_manifest_sha256",
        }

        self.assertTrue(
            forbidden.isdisjoint(fields)
        )


if __name__ == "__main__":
    unittest.main()
