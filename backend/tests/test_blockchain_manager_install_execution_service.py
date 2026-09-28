from __future__ import annotations

import ssl
import unittest

from backend.services.blockchain_manager_control_context_service import (
    BlockchainManagerControlContext,
)
from backend.services.blockchain_manager_install_execution_service import (
    BlockchainManagerInstallExecutionRequest,
    BlockchainManagerInstallExecutionService,
)
from backend.transports.blockchain_manager_control import (
    BlockchainManagerInstallRequest,
    BlockchainManagerInstallResult,
)


SECRET = "test-secret-never-durable"

SSL_CONTEXT = ssl.create_default_context()
ENDPOINT = "http://192.0.2.154:8080"


class FakeContextService:
    def __init__(
        self,
        context=None,
        error=None,
    ):
        self.context = context
        self.error = error
        self.calls = []

    def resolve(
        self,
        *,
        target_asset_id,
    ):
        self.calls.append(
            target_asset_id
        )

        if self.error:
            raise self.error

        return self.context


class FakeTransport:
    def __init__(
        self,
        result,
    ):
        self.result = result
        self.calls = []

    def install(
        self,
        *,
        endpoint,
        token,
        ssl_context,
        request,
        timeout_seconds=900,
    ):
        self.calls.append(
            {
                "endpoint":
                    endpoint,
                "token":
                    token,
                "ssl_context":
                    ssl_context,
                "request":
                    request,
                "timeout_seconds":
                    timeout_seconds,
            }
        )

        return self.result


class BlockchainManagerInstallExecutionTests(
    unittest.TestCase
):
    def context(self):
        return BlockchainManagerControlContext(
            target_asset_id="asset-154",
            endpoint_id="endpoint-bm-154",
            endpoint=ENDPOINT,
            protocol="https",
            ssl_context=SSL_CONTEXT,
            token=SECRET,
        )

    def result(
        self,
        **overrides,
    ):
        values = {
            "operation_id":
                "manager-op-001",
            "status":
                "succeeded",
            "provider_id":
                "bitcoin-mainnet",
            "storage_target_id":
                "storage-main",
            "verified":
                True,
            "duration_ms":
                321,
            "result":
                {
                    "verification": {
                        "verified": True,
                    }
                },
        }

        values.update(
            overrides
        )

        return BlockchainManagerInstallResult(
            **values
        )

    def request(self):
        return BlockchainManagerInstallExecutionRequest(
            target_asset_id="asset-154",
            provider_id="bitcoin-mainnet",
            storage_target_id="storage-main",
            storage_source="/dev/sda6",
            storage_filesystem="ext4",
        )

    def build(
        self,
        *,
        context=None,
        result=None,
    ):
        context_service = FakeContextService(
            context=(
                self.context()
                if context is None
                else context
            )
        )

        transport = FakeTransport(
            self.result()
            if result is None
            else result
        )

        factory_calls = []

        def factory():
            factory_calls.append(
                "created"
            )

            return transport

        service = (
            BlockchainManagerInstallExecutionService(
                context_service=context_service,
                transport_factory=factory,
            )
        )

        return (
            service,
            context_service,
            transport,
            factory_calls,
        )

    def test_executes_minimal_typed_install(
        self,
    ):
        (
            service,
            context_service,
            transport,
            factory_calls,
        ) = self.build()

        output = service.execute(
            self.request()
        )

        self.assertEqual(
            context_service.calls,
            ["asset-154"],
        )

        self.assertEqual(
            factory_calls,
            ["created"],
        )

        self.assertEqual(
            len(transport.calls),
            1,
        )

        call = transport.calls[0]

        self.assertEqual(
            call["endpoint"],
            ENDPOINT,
        )

        self.assertEqual(
            call["token"],
            SECRET,
        )

        sent = call["request"]

        self.assertIsInstance(
            sent,
            BlockchainManagerInstallRequest,
        )

        self.assertEqual(
            sent.provider_id,
            "bitcoin-mainnet",
        )

        self.assertEqual(
            sent.storage_target_id,
            "storage-main",
        )

        self.assertEqual(
            call["timeout_seconds"],
            900,
        )

        self.assertEqual(
            output.operation_id,
            "manager-op-001",
        )

        self.assertTrue(
            output.verified
        )

    def test_evidence_excludes_secret_and_address(
        self,
    ):
        (
            service,
            _context_service,
            _transport,
            _factory_calls,
        ) = self.build()

        output = service.execute(
            self.request()
        )

        rendered = repr(
            output.evidence
        )

        self.assertNotIn(
            SECRET,
            rendered,
        )

        self.assertNotIn(
            ENDPOINT,
            rendered,
        )

        self.assertNotIn(
            "192.0.2.154",
            rendered,
        )

        self.assertEqual(
            output.evidence[
                "endpointId"
            ],
            "endpoint-bm-154",
        )

        self.assertEqual(
            output.evidence[
                "authority"
            ],
            "blockchain-manager",
        )

    def test_context_failure_prevents_transport_factory(
        self,
    ):
        context_service = FakeContextService(
            error=ValueError(
                "credential missing"
            )
        )

        factory_calls = []

        service = (
            BlockchainManagerInstallExecutionService(
                context_service=context_service,
                transport_factory=(
                    lambda:
                        factory_calls.append(
                            "created"
                        )
                ),
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "credential missing",
        ):
            service.execute(
                self.request()
            )

        self.assertEqual(
            factory_calls,
            [],
        )

    def test_context_target_mismatch_fails_before_transport(
        self,
    ):
        context = self.context()

        wrong = BlockchainManagerControlContext(
            target_asset_id="asset-other",
            endpoint_id=context.endpoint_id,
            endpoint=context.endpoint,
            protocol="https",
            ssl_context=SSL_CONTEXT,
            token=context.token,
        )

        (
            service,
            _context_service,
            _transport,
            factory_calls,
        ) = self.build(
            context=wrong
        )

        with self.assertRaisesRegex(
            ValueError,
            "target mismatch",
        ):
            service.execute(
                self.request()
            )

        self.assertEqual(
            factory_calls,
            [],
        )

    def test_provider_mismatch_fails_closed(
        self,
    ):
        (
            service,
            _context_service,
            _transport,
            _factory_calls,
        ) = self.build(
            result=self.result(
                provider_id=(
                    "bitcoin-cash-mainnet"
                )
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "provider identity mismatch",
        ):
            service.execute(
                self.request()
            )

    def test_storage_mismatch_fails_closed(
        self,
    ):
        (
            service,
            _context_service,
            _transport,
            _factory_calls,
        ) = self.build(
            result=self.result(
                storage_target_id=(
                    "storage-other"
                )
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "storage target identity mismatch",
        ):
            service.execute(
                self.request()
            )

    def test_unverified_result_fails_closed(
        self,
    ):
        (
            service,
            _context_service,
            _transport,
            _factory_calls,
        ) = self.build(
            result=self.result(
                verified=False
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "was not verified",
        ):
            service.execute(
                self.request()
            )

    def test_failed_status_fails_closed(
        self,
    ):
        (
            service,
            _context_service,
            _transport,
            _factory_calls,
        ) = self.build(
            result=self.result(
                status="failed"
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "did not succeed",
        ):
            service.execute(
                self.request()
            )

    def test_invalid_transport_result_fails_closed(
        self,
    ):
        (
            service,
            _context_service,
            _transport,
            _factory_calls,
        ) = self.build(
            result={
                "status":
                    "succeeded"
            }
        )

        with self.assertRaisesRegex(
            ValueError,
            "invalid result",
        ):
            service.execute(
                self.request()
            )

    def test_invalid_provider_fails_before_context(
        self,
    ):
        (
            service,
            context_service,
            _transport,
            factory_calls,
        ) = self.build()

        request = (
            BlockchainManagerInstallExecutionRequest(
                target_asset_id="asset-154",
                provider_id="../bad",
                storage_target_id="storage-main",
                storage_source="/dev/sda6",
                storage_filesystem="ext4",
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "provider_id is invalid",
        ):
            service.execute(
                request
            )

        self.assertEqual(
            context_service.calls,
            [],
        )

        self.assertEqual(
            factory_calls,
            [],
        )

    def test_invalid_storage_fails_before_context(
        self,
    ):
        (
            service,
            context_service,
            _transport,
            factory_calls,
        ) = self.build()

        request = (
            BlockchainManagerInstallExecutionRequest(
                target_asset_id="asset-154",
                provider_id="bitcoin-mainnet",
                storage_target_id="../bad",
                storage_source="/dev/sda6",
                storage_filesystem="ext4",
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "storage_target_id is invalid",
        ):
            service.execute(
                request
            )

        self.assertEqual(
            context_service.calls,
            [],
        )

        self.assertEqual(
            factory_calls,
            [],
        )


if __name__ == "__main__":
    unittest.main()
