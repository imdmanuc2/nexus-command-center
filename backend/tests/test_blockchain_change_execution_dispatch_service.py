import unittest

from backend.core.operation_execution_control import (
    OperationCancellationRequested,
    OperationLeaseLost,
)

from backend.executors.blockchain_deployment_executor import (
    DeploymentResult,
    DeploymentStepResult,
)
from backend.services.blockchain_change_execution_dispatch_service import (
    BlockchainChangeExecutionDispatchError,
    BlockchainChangeExecutionDispatchService,
)


class _Adapter:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def execute(self, operation, change, worker_id):
        self.calls.append(
            (operation, change, worker_id)
        )
        return self.result


class BlockchainChangeExecutionDispatchServiceTests(
    unittest.TestCase
):
    def result(self, status="completed", error=None):
        return DeploymentResult(
            status=status,
            provider_id="bitcoin-mainnet",
            storage_target_id="storage-main",
            target_asset_id="asset-test",
            correlation_id="corr-test",
            approved_by="approval-test",
            duration_ms=123,
            steps=(
                DeploymentStepResult(
                    step_id="resolve-release",
                    status=(
                        "completed"
                        if status == "completed"
                        else "failed"
                    ),
                    duration_ms=10,
                    evidence={"releaseId": "release-test"},
                ),
            ),
            error=error,
        )

    def operation(self):
        return {
            "operation_id": "op-test",
            "action_name": "blockchain.install",
        }

    def change(self):
        return {
            "operation_id": "op-test",
            "status": "executing",
            "approval_required": True,
            "approved_by": "approval-test",
            "capability": "blockchain.install",
        }

    def test_dispatches_only_blockchain_install(self):
        adapter = _Adapter(self.result())
        service = BlockchainChangeExecutionDispatchService(
            adapter_factory=lambda: adapter,
        )

        result = service.execute(
            self.operation(),
            self.change(),
            "worker-test",
        )

        self.assertTrue(result.ok)
        self.assertEqual(
            adapter.calls,
            [
                (
                    self.operation(),
                    self.change(),
                    "worker-test",
                )
            ],
        )

    def test_wrong_action_fails_before_adapter_factory(self):
        calls = []

        service = BlockchainChangeExecutionDispatchService(
            adapter_factory=lambda: calls.append(True),
        )

        operation = self.operation()
        operation["action_name"] = "linux.service.restart"

        with self.assertRaisesRegex(
            BlockchainChangeExecutionDispatchError,
            "Unsupported specialized operation action",
        ):
            service.execute(
                operation,
                self.change(),
                "worker-test",
            )

        self.assertEqual(calls, [])

    def test_missing_worker_fails_before_adapter_factory(self):
        calls = []

        service = BlockchainChangeExecutionDispatchService(
            adapter_factory=lambda: calls.append(True),
        )

        with self.assertRaisesRegex(
            BlockchainChangeExecutionDispatchError,
            "worker_id is required",
        ):
            service.execute(
                self.operation(),
                self.change(),
                "",
            )

        self.assertEqual(calls, [])

    def test_invalid_adapter_fails_closed(self):
        service = BlockchainChangeExecutionDispatchService(
            adapter_factory=lambda: object(),
        )

        with self.assertRaisesRegex(
            BlockchainChangeExecutionDispatchError,
            "adapter is invalid",
        ):
            service.execute(
                self.operation(),
                self.change(),
                "worker-test",
            )

    def test_invalid_adapter_result_fails_closed(self):
        adapter = _Adapter({"status": "completed"})

        service = BlockchainChangeExecutionDispatchService(
            adapter_factory=lambda: adapter,
        )

        with self.assertRaisesRegex(
            BlockchainChangeExecutionDispatchError,
            "returned invalid result",
        ):
            service.execute(
                self.operation(),
                self.change(),
                "worker-test",
            )

    def test_success_result_projects_to_existing_result_data(self):
        result = self.result()

        payload = (
            BlockchainChangeExecutionDispatchService
            .result_data(result)
        )

        self.assertEqual(
            payload["status"],
            "completed",
        )
        self.assertEqual(
            payload["providerId"],
            "bitcoin-mainnet",
        )
        self.assertEqual(
            payload["storageTargetId"],
            "storage-main",
        )
        self.assertEqual(
            payload["targetAssetId"],
            "asset-test",
        )
        self.assertEqual(
            payload["correlationId"],
            "corr-test",
        )
        self.assertEqual(
            payload["approvedBy"],
            "approval-test",
        )
        self.assertEqual(
            payload["durationMs"],
            123,
        )
        self.assertEqual(
            payload["steps"][0]["stepId"],
            "resolve-release",
        )
        self.assertIsNone(payload["error"])

    def test_failed_result_preserves_error_and_step_evidence(self):
        result = self.result(
            status="failed",
            error=(
                "verify-runtime: "
                "Operation cancellation requested"
            ),
        )

        payload = (
            BlockchainChangeExecutionDispatchService
            .result_data(result)
        )

        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            payload["error"],
            (
                "verify-runtime: "
                "Operation cancellation requested"
            ),
        )
        self.assertEqual(
            payload["steps"][0]["status"],
            "failed",
        )
        self.assertEqual(
            payload["steps"][0]["evidence"],
            {"releaseId": "release-test"},
        )

    def test_projection_rejects_non_deployment_result(self):
        with self.assertRaisesRegex(
            BlockchainChangeExecutionDispatchError,
            "Deployment result is invalid",
        ):
            (
                BlockchainChangeExecutionDispatchService
                .result_data({})
            )


    def test_typed_cancellation_propagates_through_dispatch(self):
        class CancellingAdapter:
            def execute(
                self,
                operation,
                change,
                worker_id,
            ):
                del operation
                del change
                del worker_id
                raise OperationCancellationRequested(
                    "Operation cancellation requested"
                )

        service = BlockchainChangeExecutionDispatchService(
            adapter_factory=lambda: CancellingAdapter()
        )

        with self.assertRaisesRegex(
            OperationCancellationRequested,
            "cancellation requested",
        ):
            service.execute(
                self.operation(),
                self.change(),
                "worker-1",
            )

    def test_typed_lease_loss_propagates_through_dispatch(self):
        class LeaseLostAdapter:
            def execute(
                self,
                operation,
                change,
                worker_id,
            ):
                del operation
                del change
                del worker_id
                raise OperationLeaseLost(
                    "Operation lease ownership was lost"
                )

        service = BlockchainChangeExecutionDispatchService(
            adapter_factory=lambda: LeaseLostAdapter()
        )

        with self.assertRaisesRegex(
            OperationLeaseLost,
            "lease ownership was lost",
        ):
            service.execute(
                self.operation(),
                self.change(),
                "worker-1",
            )


if __name__ == "__main__":
    unittest.main()
