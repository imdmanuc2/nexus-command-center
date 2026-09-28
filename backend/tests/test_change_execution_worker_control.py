from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from backend.core.operation_execution_control import (
    OperationCancellationRequested,
    OperationLeaseLost,
)
from backend.services import change_execution_service as service


class _Capability:
    requires_approval = False
    timeout_seconds = 60
    verify_argv = None

    def build_argv(self, parameters):
        del parameters
        return ("/usr/bin/true",)


class _Registry:
    def resolve(self, action_name):
        self.action_name = action_name
        return _Capability()

    def validate_parameters(
        self,
        capability,
        parameters,
    ):
        del capability
        del parameters


class _TransportResult:
    def __init__(self):
        self.ok = True
        self.exit_code = 0
        self.stderr = ""

    def to_dict(self):
        return {
            "success": True,
            "exitCode": 0,
            "durationMs": 10,
            "transport": "test",
            "stdout": "",
            "stderr": "",
            "timedOut": False,
        }


class _Transport:
    def execute(
        self,
        *,
        target,
        argv,
        timeout_seconds,
    ):
        del target
        del argv
        del timeout_seconds
        return _TransportResult()


class _TransportRegistry:
    def resolve(self, transport):
        del transport
        return _Transport()


class _Target:
    transport = "ssh"


class ChangeExecutionWorkerControlTests(
    unittest.TestCase
):
    def operation(self):
        return {
            "operation_id": "op-control-1",
            "action_name": "test.capability",
            "input_data": {
                "parameters": {},
            },
            "asset_id": "asset-control-1",
            "target_id": "asset-control-1",
            "timeout_seconds": 60,
            "confirmed": True,
        }

    def change(self):
        return {
            "change_id": "chg-control-1",
            "operation_id": "op-control-1",
        }

    def base_patches(self):
        return (
            patch.object(
                service.repo,
                "find_change_for_operation",
                return_value=self.change(),
            ),
            patch.object(
                service.repo,
                "start_attempt",
                return_value="attempt-control-1",
            ),
            patch.object(
                service,
                "get_capability_registry",
                return_value=_Registry(),
            ),
            patch.object(
                service,
                "resolve_target",
                return_value=_Target(),
            ),
            patch.object(
                service,
                "get_transport_registry",
                return_value=_TransportRegistry(),
            ),
        )

    def test_success_passes_worker_identity_to_finalizer(
        self,
    ):
        (
            p_change,
            p_attempt,
            p_registry,
            p_target,
            p_transport,
        ) = self.base_patches()

        with (
            p_change,
            p_attempt,
            p_registry,
            p_target,
            p_transport,
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
                self.operation(),
                "worker-control-1",
            )

        self.assertEqual(
            result["status"],
            "succeeded",
        )

        finish_failure.assert_not_called()
        finish_cancelled.assert_not_called()

        finish_success.assert_called_once()

        args = finish_success.call_args.args

        self.assertEqual(
            args[0],
            "attempt-control-1",
        )
        self.assertEqual(
            args[-1],
            "worker-control-1",
        )

    def test_cancellation_uses_cancelled_finalizer(
        self,
    ):
        operation = self.operation()

        with (
            patch.object(
                service.repo,
                "find_change_for_operation",
                return_value=self.change(),
            ),
            patch.object(
                service.repo,
                "start_attempt",
                return_value="attempt-control-1",
            ),
            patch.object(
                service,
                "get_capability_registry",
                side_effect=OperationCancellationRequested(
                    "Operation cancellation requested"
                ),
            ),
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
                "worker-control-1",
            )

        self.assertEqual(
            result["status"],
            "cancelled",
        )

        finish_success.assert_not_called()
        finish_failure.assert_not_called()

        finish_cancelled.assert_called_once_with(
            "attempt-control-1",
            operation,
            self.change(),
            "worker-control-1",
            "Operation cancellation requested",
        )

    def test_lease_loss_does_not_finalize(self):
        operation = self.operation()

        with (
            patch.object(
                service.repo,
                "find_change_for_operation",
                return_value=self.change(),
            ),
            patch.object(
                service.repo,
                "start_attempt",
                return_value="attempt-control-1",
            ),
            patch.object(
                service,
                "get_capability_registry",
                side_effect=OperationLeaseLost(
                    "Operation lease ownership was lost"
                ),
            ),
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
                "worker-control-1",
            )

        self.assertEqual(
            result["status"],
            "lease-lost",
        )

        finish_success.assert_not_called()
        finish_failure.assert_not_called()
        finish_cancelled.assert_not_called()

    def test_cancel_finalizer_lease_loss_stops_cleanly(
        self,
    ):
        operation = self.operation()

        with (
            patch.object(
                service.repo,
                "find_change_for_operation",
                return_value=self.change(),
            ),
            patch.object(
                service.repo,
                "start_attempt",
                return_value="attempt-control-1",
            ),
            patch.object(
                service,
                "get_capability_registry",
                side_effect=OperationCancellationRequested(
                    "Operation cancellation requested"
                ),
            ),
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
                side_effect=OperationLeaseLost(
                    "Operation terminal finalization lost ownership"
                ),
            ) as finish_cancelled,
        ):
            result = service.execute_operation(
                operation,
                "worker-control-1",
            )

        self.assertEqual(
            result["status"],
            "lease-lost",
        )

        finish_success.assert_not_called()
        finish_failure.assert_not_called()
        finish_cancelled.assert_called_once()

    def test_failure_finalizer_lease_loss_stops_cleanly(
        self,
    ):
        operation = self.operation()

        with (
            patch.object(
                service.repo,
                "find_change_for_operation",
                return_value=self.change(),
            ),
            patch.object(
                service.repo,
                "start_attempt",
                return_value="attempt-control-1",
            ),
            patch.object(
                service,
                "get_capability_registry",
                side_effect=RuntimeError(
                    "target failure"
                ),
            ),
            patch.object(
                service.repo,
                "finish_success",
            ) as finish_success,
            patch.object(
                service.repo,
                "finish_failure",
                side_effect=OperationLeaseLost(
                    "Operation terminal finalization lost ownership"
                ),
            ) as finish_failure,
            patch.object(
                service.repo,
                "finish_cancelled",
            ) as finish_cancelled,
        ):
            result = service.execute_operation(
                operation,
                "worker-control-1",
            )

        self.assertEqual(
            result["status"],
            "lease-lost",
        )

        finish_success.assert_not_called()
        finish_cancelled.assert_not_called()
        finish_failure.assert_called_once()

        args = finish_failure.call_args.args

        self.assertEqual(
            args[-1],
            "worker-control-1",
        )


if __name__ == "__main__":
    unittest.main()
