from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from backend.core.operation_execution_control import (
    OperationCancellationRequested,
    OperationLeaseLost,
)
from backend.executors.blockchain_deployment_executor import (
    DeploymentResult,
    DeploymentStepResult,
)
from backend.services import change_execution_service as service


class _Dispatch:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def execute(
        self,
        operation,
        change,
        worker_id,
    ):
        self.calls.append(
            (operation, change, worker_id)
        )

        if self.error is not None:
            raise self.error

        return self.result

    def result_data(self, result):
        return result.to_dict()


class ChangeExecutionBlockchainDispatchTests(
    unittest.TestCase
):
    def operation(self):
        return {
            "operation_id": "op-blockchain-1",
            "action_name": "blockchain.install",
            "target_type": "asset",
            "target_id": "asset-managed-1",
            "asset_id": "asset-managed-1",
            "correlation_id": "corr-blockchain-1",
            "confirmed": True,
            "confirmed_by": "queue-operator",
            "input_data": {
                "parameters": {
                    "providerId": "bitcoin-mainnet",
                    "storageTargetId": "storage-main",
                }
            },
        }

    def change(self):
        return {
            "change_id": "chg-blockchain-1",
            "operation_id": "op-blockchain-1",
            "status": "executing",
            "approval_required": True,
            "approved_by": "change-approver",
            "capability": "blockchain.install",
        }

    def deployment_result(
        self,
        *,
        status="completed",
        error=None,
    ):
        return DeploymentResult(
            status=status,
            provider_id="bitcoin-mainnet",
            storage_target_id="storage-main",
            target_asset_id="asset-managed-1",
            correlation_id="corr-blockchain-1",
            approved_by="change-approver",
            duration_ms=100,
            steps=(
                DeploymentStepResult(
                    step_id="resolve-release",
                    status=(
                        "completed"
                        if status == "completed"
                        else "failed"
                    ),
                    duration_ms=10,
                    evidence={
                        "releaseId": "release-test"
                    },
                ),
            ),
            error=error,
        )

    def test_blockchain_install_uses_specialized_dispatch_only(
        self,
    ):
        operation = self.operation()
        change = self.change()

        dispatch = _Dispatch(
            self.deployment_result()
        )

        with (
            patch.object(
                service.repo,
                "find_change_for_operation",
                return_value=change,
            ),
            patch.object(
                service.repo,
                "start_attempt",
                return_value="attempt-blockchain-1",
            ),
            patch.object(
                service,
                "_blockchain_install_dispatch",
                return_value=dispatch,
            ),
            patch.object(
                service,
                "get_capability_registry",
            ) as generic_registry,
            patch.object(
                service.repo,
                "finish_success",
            ) as finish_success,
            patch.object(
                service.repo,
                "finish_failure",
            ) as finish_failure,
            patch.object(
                service.repo,
                "finish_cancelled",
            ) as finish_cancelled,
        ):
            result = service.execute_operation(
                operation,
                "worker-blockchain-1",
            )

        self.assertEqual(
            result["status"],
            "succeeded",
        )

        generic_registry.assert_not_called()
        finish_failure.assert_not_called()
        finish_cancelled.assert_not_called()

        self.assertEqual(
            dispatch.calls,
            [
                (
                    operation,
                    change,
                    "worker-blockchain-1",
                )
            ],
        )

        finish_success.assert_called_once()

        args = finish_success.call_args.args

        self.assertEqual(
            args[0],
            "attempt-blockchain-1",
        )
        self.assertEqual(
            args[1],
            operation,
        )
        self.assertEqual(
            args[2],
            change,
        )
        self.assertEqual(
            args[-1],
            "worker-blockchain-1",
        )

        projected = args[3]

        self.assertEqual(
            projected["status"],
            "completed",
        )
        self.assertEqual(
            projected["providerId"],
            "bitcoin-mainnet",
        )
        self.assertEqual(
            projected["approvedBy"],
            "change-approver",
        )

    def test_failed_deployment_uses_normal_failure_finalizer(
        self,
    ):
        operation = self.operation()
        change = self.change()

        dispatch = _Dispatch(
            self.deployment_result(
                status="failed",
                error="verify-runtime failed",
            )
        )

        with (
            patch.object(
                service.repo,
                "find_change_for_operation",
                return_value=change,
            ),
            patch.object(
                service.repo,
                "start_attempt",
                return_value="attempt-blockchain-1",
            ),
            patch.object(
                service,
                "_blockchain_install_dispatch",
                return_value=dispatch,
            ),
            patch.object(
                service,
                "get_capability_registry",
            ) as generic_registry,
            patch.object(
                service.repo,
                "finish_success",
            ) as finish_success,
            patch.object(
                service.repo,
                "finish_failure",
            ) as finish_failure,
            patch.object(
                service.repo,
                "finish_cancelled",
            ) as finish_cancelled,
        ):
            result = service.execute_operation(
                operation,
                "worker-blockchain-1",
            )

        self.assertEqual(
            result["status"],
            "failed",
        )

        generic_registry.assert_not_called()
        finish_success.assert_not_called()
        finish_cancelled.assert_not_called()
        finish_failure.assert_called_once()

        args = finish_failure.call_args.args

        self.assertEqual(
            args[0],
            "attempt-blockchain-1",
        )
        self.assertEqual(
            args[3],
            "verify-runtime failed",
        )
        self.assertEqual(
            args[4]["status"],
            "failed",
        )
        self.assertEqual(
            args[-1],
            "worker-blockchain-1",
        )

    def test_specialized_cancellation_reaches_cancel_finalizer(
        self,
    ):
        operation = self.operation()
        change = self.change()

        dispatch = _Dispatch(
            error=OperationCancellationRequested(
                "Operation cancellation requested"
            )
        )

        with (
            patch.object(
                service.repo,
                "find_change_for_operation",
                return_value=change,
            ),
            patch.object(
                service.repo,
                "start_attempt",
                return_value="attempt-blockchain-1",
            ),
            patch.object(
                service,
                "_blockchain_install_dispatch",
                return_value=dispatch,
            ),
            patch.object(
                service,
                "get_capability_registry",
            ) as generic_registry,
            patch.object(
                service.repo,
                "finish_success",
            ) as finish_success,
            patch.object(
                service.repo,
                "finish_failure",
            ) as finish_failure,
            patch.object(
                service.repo,
                "finish_cancelled",
            ) as finish_cancelled,
        ):
            result = service.execute_operation(
                operation,
                "worker-blockchain-1",
            )

        self.assertEqual(
            result["status"],
            "cancelled",
        )

        generic_registry.assert_not_called()
        finish_success.assert_not_called()
        finish_failure.assert_not_called()

        finish_cancelled.assert_called_once_with(
            "attempt-blockchain-1",
            operation,
            change,
            "worker-blockchain-1",
            "Operation cancellation requested",
        )

    def test_specialized_lease_loss_never_finalizes(
        self,
    ):
        operation = self.operation()
        change = self.change()

        dispatch = _Dispatch(
            error=OperationLeaseLost(
                "Operation lease ownership was lost"
            )
        )

        with (
            patch.object(
                service.repo,
                "find_change_for_operation",
                return_value=change,
            ),
            patch.object(
                service.repo,
                "start_attempt",
                return_value="attempt-blockchain-1",
            ),
            patch.object(
                service,
                "_blockchain_install_dispatch",
                return_value=dispatch,
            ),
            patch.object(
                service,
                "get_capability_registry",
            ) as generic_registry,
            patch.object(
                service.repo,
                "finish_success",
            ) as finish_success,
            patch.object(
                service.repo,
                "finish_failure",
            ) as finish_failure,
            patch.object(
                service.repo,
                "finish_cancelled",
            ) as finish_cancelled,
        ):
            result = service.execute_operation(
                operation,
                "worker-blockchain-1",
            )

        self.assertEqual(
            result["status"],
            "lease-lost",
        )

        generic_registry.assert_not_called()
        finish_success.assert_not_called()
        finish_failure.assert_not_called()
        finish_cancelled.assert_not_called()

    def test_non_blockchain_action_does_not_construct_dispatch(
        self,
    ):
        operation = self.operation()
        operation["action_name"] = "linux.service.restart"

        capability = MagicMock()
        capability.requires_approval = False
        capability.timeout_seconds = 30
        capability.verify_argv = None
        capability.build_argv.return_value = (
            "/usr/bin/true",
        )

        registry = MagicMock()
        registry.resolve.return_value = capability

        target = MagicMock()
        target.transport = "ssh"

        transport_result = MagicMock()
        transport_result.ok = True
        transport_result.exit_code = 0
        transport_result.stderr = ""
        transport_result.to_dict.return_value = {
            "exitCode": 0,
            "timedOut": False,
            "transport": "test",
            "stdout": "",
            "stderr": "",
        }

        transport = MagicMock()
        transport.execute.return_value = (
            transport_result
        )

        transport_registry = MagicMock()
        transport_registry.resolve.return_value = (
            transport
        )

        with (
            patch.object(
                service.repo,
                "find_change_for_operation",
                return_value=None,
            ),
            patch.object(
                service.repo,
                "start_attempt",
                return_value="attempt-generic-1",
            ),
            patch.object(
                service,
                "_blockchain_install_dispatch",
            ) as specialized_factory,
            patch.object(
                service,
                "get_capability_registry",
                return_value=registry,
            ),
            patch.object(
                service,
                "resolve_target",
                return_value=target,
            ),
            patch.object(
                service,
                "get_transport_registry",
                return_value=transport_registry,
            ),
            patch.object(
                service.repo,
                "finish_success",
            ),
        ):
            result = service.execute_operation(
                operation,
                "worker-generic-1",
            )

        self.assertEqual(
            result["status"],
            "succeeded",
        )

        specialized_factory.assert_not_called()
        registry.resolve.assert_called_once_with(
            "linux.service.restart"
        )


if __name__ == "__main__":
    unittest.main()
