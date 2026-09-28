from __future__ import annotations

import unittest

from backend.core.operation_execution_control import (
    OperationCancellationRequested,
    OperationLeaseLost,
)

from backend.executors.blockchain_deployment_executor import (
    BlockchainDeploymentExecutor,
    DeploymentRequest,
    DeploymentStepOutput,
)


class BlockchainDeploymentExecutionControlTests(
    unittest.TestCase
):
    def _request(self):
        return DeploymentRequest(
            provider_id="bitcoin-mainnet",
            storage_target_id="storage-main",
            target_asset_id="asset-target",
            correlation_id="corr-control",
            approved_by="operator",
        )

    def _executor(self, calls, control=None):
        def resolve(request):
            del request
            calls.append("resolve-release")
            return DeploymentStepOutput(
                evidence={
                    "step": "resolve-release",
                }
            )

        def later(name):
            def handler(
                request,
                evidence_context,
                private_context,
            ):
                del request
                del evidence_context
                del private_context
                calls.append(name)
                return DeploymentStepOutput(
                    evidence={"step": name}
                )

            return handler

        return BlockchainDeploymentExecutor(
            resolve_release=resolve,
            transfer_bootstrap=later(
                "transfer-bootstrap"
            ),
            transfer_runtime=later(
                "transfer-runtime"
            ),
            invoke_bootstrap=later(
                "invoke-bootstrap"
            ),
            verify_runtime=later(
                "verify-runtime"
            ),
            invoke_installer=later(
                "invoke-installer"
            ),
            verify_installation=later(
                "verify-installation"
            ),
            execution_control=control,
        )

    def test_control_runs_before_every_step(self):
        handlers = []
        controls = []

        def control(
            request,
            step_id,
            step_number,
            total_steps,
        ):
            controls.append(
                (
                    request.correlation_id,
                    step_id,
                    step_number,
                    total_steps,
                )
            )

        result = self._executor(
            handlers,
            control,
        ).execute(self._request())

        self.assertTrue(result.ok, result.error)

        self.assertEqual(
            handlers,
            list(
                BlockchainDeploymentExecutor.STEP_IDS
            ),
        )

        self.assertEqual(
            [item[1] for item in controls],
            list(
                BlockchainDeploymentExecutor.STEP_IDS
            ),
        )

        self.assertEqual(
            [item[2] for item in controls],
            list(range(1, 8)),
        )

        self.assertTrue(
            all(item[3] == 7 for item in controls)
        )

    def test_control_can_stop_before_first_step(self):
        handlers = []

        def control(
            request,
            step_id,
            step_number,
            total_steps,
        ):
            del request
            del step_number
            del total_steps

            if step_id == "resolve-release":
                raise RuntimeError(
                    "Deployment cancellation requested"
                )

        result = self._executor(
            handlers,
            control,
        ).execute(self._request())

        self.assertFalse(result.ok)
        self.assertEqual(handlers, [])
        self.assertEqual(
            len(result.steps),
            1,
        )
        self.assertEqual(
            result.steps[0].step_id,
            "resolve-release",
        )
        self.assertEqual(
            result.steps[0].status,
            "failed",
        )
        self.assertIn(
            "Deployment cancellation requested",
            result.error or "",
        )

    def test_control_stops_before_requested_next_step(self):
        handlers = []
        controls = []

        def control(
            request,
            step_id,
            step_number,
            total_steps,
        ):
            del request
            del total_steps

            controls.append(
                (step_id, step_number)
            )

            if step_id == "transfer-runtime":
                raise RuntimeError(
                    "Deployment cancellation requested"
                )

        result = self._executor(
            handlers,
            control,
        ).execute(self._request())

        self.assertFalse(result.ok)

        self.assertEqual(
            handlers,
            [
                "resolve-release",
                "transfer-bootstrap",
            ],
        )

        self.assertEqual(
            controls,
            [
                ("resolve-release", 1),
                ("transfer-bootstrap", 2),
                ("transfer-runtime", 3),
            ],
        )

        self.assertEqual(
            [step.step_id for step in result.steps],
            [
                "resolve-release",
                "transfer-bootstrap",
                "transfer-runtime",
            ],
        )

        self.assertEqual(
            result.steps[-1].status,
            "failed",
        )

    def test_no_control_preserves_existing_behavior(self):
        handlers = []

        result = self._executor(
            handlers
        ).execute(self._request())

        self.assertTrue(result.ok, result.error)
        self.assertEqual(
            len(result.steps),
            7,
        )
        self.assertTrue(
            all(step.ok for step in result.steps)
        )


    def test_typed_cancellation_propagates_without_deployment_failure(self):
        handlers = []

        def control(
            request,
            step_id,
            step_number,
            total_steps,
        ):
            del request
            del step_number
            del total_steps

            if step_id == "transfer-runtime":
                raise OperationCancellationRequested(
                    "Operation cancellation requested"
                )

        with self.assertRaisesRegex(
            OperationCancellationRequested,
            "cancellation requested",
        ):
            self._executor(
                handlers,
                control,
            ).execute(self._request())

        self.assertEqual(
            handlers,
            [
                "resolve-release",
                "transfer-bootstrap",
            ],
        )

    def test_typed_lease_loss_propagates_without_deployment_failure(self):
        handlers = []

        def control(
            request,
            step_id,
            step_number,
            total_steps,
        ):
            del request
            del step_number
            del total_steps

            if step_id == "transfer-runtime":
                raise OperationLeaseLost(
                    "Operation lease ownership was lost"
                )

        with self.assertRaisesRegex(
            OperationLeaseLost,
            "lease ownership was lost",
        ):
            self._executor(
                handlers,
                control,
            ).execute(self._request())

        self.assertEqual(
            handlers,
            [
                "resolve-release",
                "transfer-bootstrap",
            ],
        )


if __name__ == "__main__":
    unittest.main()
