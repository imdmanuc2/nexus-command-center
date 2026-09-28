from __future__ import annotations

import unittest

from backend.core.operation_execution_control import (
    OperationCancellationRequested,
    OperationLeaseLost,
)
from unittest.mock import MagicMock

from backend.executors.blockchain_deployment_executor import (
    BlockchainDeploymentExecutor,
    DeploymentRequest,
    DeploymentStepOutput,
)
from backend.services.blockchain_change_execution_adapter import (
    BlockchainChangeExecutionAdapter,
    BlockchainChangeExecutionAdapterError,
)


class BlockchainChangeExecutionAdapterTests(
    unittest.TestCase
):
    def _operation(self, **overrides):
        operation = {
            "operation_id": "change-123",
            "action_name": "blockchain.install",
            "target_type": "asset",
            "target_id": "asset-managed-1",
            "asset_id": "asset-managed-1",
            "correlation_id": "corr-123",
            "confirmed": True,
            "confirmed_by": "operator",
            "input_data": {
                "changeId": "change-id-123",
                "parameters": {
                    "providerId": "bitcoin-mainnet",
                    "storageTargetId": "storage-main",
                },
            },
        }
        operation.update(overrides)
        return operation

    def _change(self, **overrides):
        change = {
            "operation_id": "change-123",
            "status": "executing",
            "approval_required": True,
            "approved_by": "change-approver",
            "capability": "blockchain.install",
        }
        change.update(overrides)
        return change

    def _executor(self, control):
        def resolve(request):
            del request
            return DeploymentStepOutput(
                evidence={"release": "reviewed"}
            )

        def later(name):
            def handler(
                request,
                evidence,
                private,
            ):
                del request
                del evidence
                del private
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

    def _adapter(self):
        checkpoints = []

        def checkpoint(
            operation_id,
            worker_id,
            current_step,
            total_steps,
            lease_seconds,
        ):
            checkpoints.append(
                (
                    operation_id,
                    worker_id,
                    current_step,
                    total_steps,
                    lease_seconds,
                )
            )
            return {
                "operation_id": operation_id,
                "status": "running",
            }

        preflight = MagicMock()
        preflight.verify.return_value = (
            object()
        )

        assembly = MagicMock()

        def assemble(
            *,
            request,
            preflight,
            execution_control,
        ):
            del request
            del preflight
            return self._executor(
                execution_control
            )

        assembly.assemble.side_effect = assemble

        adapter = BlockchainChangeExecutionAdapter(
            preflight_service=preflight,
            assembly_service=assembly,
            checkpoint=checkpoint,
            lease_seconds=120,
            platform_asset_loader=(
                lambda asset_id: {
                    "status": "ok",
                    "asset": {
                        "id": asset_id,
                        "managed": True,
                        "deploymentPlatformId":
                            "linux",
                    },
                }
            ),
        )

        return (
            adapter,
            checkpoints,
            preflight,
            assembly,
        )

    def test_maps_operations_row_to_request(self):
        adapter, _, preflight, assembly = (
            self._adapter()
        )

        result = adapter.execute(
            self._operation(),
            self._change(),
            "worker-1",
        )

        self.assertTrue(
            result.ok,
            result.error,
        )

        request = (
            preflight.verify.call_args.args[0]
        )

        self.assertEqual(
            request,
            DeploymentRequest(
                provider_id="bitcoin-mainnet",
                storage_target_id="storage-main",
                target_asset_id="asset-managed-1",
                correlation_id="corr-123",
                approved_by="change-approver",
            ),
        )

        assembled_request = (
            assembly.assemble
            .call_args.kwargs["request"]
        )

        self.assertEqual(
            assembled_request,
            request,
        )

    def test_preflight_occurs_after_operations_gate(self):
        order = []

        def checkpoint(*_args):
            order.append("checkpoint")

        preflight = MagicMock()

        def verify(_request):
            order.append("preflight")
            return object()

        preflight.verify.side_effect = verify

        assembly = MagicMock()

        def assemble(
            *,
            request,
            preflight,
            execution_control,
        ):
            del request
            del preflight
            order.append("assemble")
            return self._executor(
                execution_control
            )

        assembly.assemble.side_effect = assemble

        adapter = BlockchainChangeExecutionAdapter(
            preflight_service=preflight,
            assembly_service=assembly,
            checkpoint=checkpoint,
            platform_asset_loader=(
                lambda asset_id: {
                    "status": "ok",
                    "asset": {
                        "id": asset_id,
                        "managed": True,
                        "deploymentPlatformId":
                            "linux",
                    },
                }
            ),
        )

        result = adapter.execute(
            self._operation(),
            self._change(),
            "worker-1",
        )

        self.assertTrue(result.ok)

        self.assertEqual(
            order[:3],
            [
                "checkpoint",
                "preflight",
                "assemble",
            ],
        )

    def test_checkpoints_preflight_and_all_steps(self):
        adapter, checkpoints, _, _ = (
            self._adapter()
        )

        result = adapter.execute(
            self._operation(),
            self._change(),
            "worker-1",
        )

        self.assertTrue(result.ok)

        self.assertEqual(
            len(checkpoints),
            8,
        )

        self.assertEqual(
            checkpoints[0],
            (
                "change-123",
                "worker-1",
                1,
                7,
                120,
            ),
        )

        self.assertEqual(
            [item[2] for item in checkpoints[1:]],
            list(range(1, 8)),
        )

        self.assertTrue(
            all(
                item[3] == 7
                for item in checkpoints
            )
        )

    def test_unconfirmed_operation_fails_before_preflight(self):
        adapter, checkpoints, preflight, _ = (
            self._adapter()
        )

        with self.assertRaisesRegex(
            BlockchainChangeExecutionAdapterError,
            "confirmed approval",
        ):
            adapter.execute(
                self._operation(
                    confirmed=False
                ),
                self._change(),
                "worker-1",
            )

        self.assertEqual(
            checkpoints,
            [],
        )

        preflight.verify.assert_not_called()

    def test_wrong_action_fails_before_preflight(self):
        adapter, checkpoints, preflight, _ = (
            self._adapter()
        )

        with self.assertRaisesRegex(
            BlockchainChangeExecutionAdapterError,
            "not blockchain.install",
        ):
            adapter.execute(
                self._operation(
                    action_name="service.restart"
                ),
                self._change(),
                "worker-1",
            )

        self.assertEqual(
            checkpoints,
            [],
        )

        preflight.verify.assert_not_called()

    def test_non_asset_target_fails_closed(self):
        adapter, _, preflight, _ = (
            self._adapter()
        )

        with self.assertRaisesRegex(
            BlockchainChangeExecutionAdapterError,
            "target must be an asset",
        ):
            adapter.execute(
                self._operation(
                    target_type="service"
                ),
                self._change(),
                "worker-1",
            )

        preflight.verify.assert_not_called()

    def test_target_mismatch_fails_closed(self):
        adapter, _, preflight, _ = (
            self._adapter()
        )

        with self.assertRaisesRegex(
            BlockchainChangeExecutionAdapterError,
            "does not match asset",
        ):
            adapter.execute(
                self._operation(
                    target_id="asset-other"
                ),
                self._change(),
                "worker-1",
            )

        preflight.verify.assert_not_called()

    def test_extra_parameter_fails_capability_policy(self):
        adapter, _, preflight, _ = (
            self._adapter()
        )

        operation = self._operation()
        operation["input_data"]["parameters"][
            "command"
        ] = "whoami"

        with self.assertRaises(ValueError):
            adapter.execute(
                operation,
                self._change(),
                "worker-1",
            )

        preflight.verify.assert_not_called()

    def test_checkpoint_failure_stops_before_preflight(self):
        preflight = MagicMock()
        assembly = MagicMock()

        def checkpoint(*_args):
            raise RuntimeError(
                "Operation cancellation requested"
            )

        adapter = BlockchainChangeExecutionAdapter(
            preflight_service=preflight,
            assembly_service=assembly,
            checkpoint=checkpoint,
            platform_asset_loader=(
                lambda asset_id: {
                    "status": "ok",
                    "asset": {
                        "id": asset_id,
                        "managed": True,
                        "deploymentPlatformId":
                            "linux",
                    },
                }
            ),
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "cancellation requested",
        ):
            adapter.execute(
                self._operation(),
                self._change(),
                "worker-1",
            )

        preflight.verify.assert_not_called()
        assembly.assemble.assert_not_called()

    def test_step_checkpoint_failure_stops_executor(self):
        calls = 0

        def checkpoint(
            operation_id,
            worker_id,
            current_step,
            total_steps,
            lease_seconds,
        ):
            nonlocal calls
            del operation_id
            del worker_id
            del total_steps
            del lease_seconds

            calls += 1

            # First call is preflight.
            # Stop before durable step 3.
            if calls == 4:
                raise RuntimeError(
                    "Operation cancellation requested"
                )

        preflight = MagicMock()
        preflight.verify.return_value = object()

        assembly = MagicMock()

        def assemble(
            *,
            request,
            preflight,
            execution_control,
        ):
            del request
            del preflight
            return self._executor(
                execution_control
            )

        assembly.assemble.side_effect = assemble

        adapter = BlockchainChangeExecutionAdapter(
            preflight_service=preflight,
            assembly_service=assembly,
            checkpoint=checkpoint,
            platform_asset_loader=(
                lambda asset_id: {
                    "status": "ok",
                    "asset": {
                        "id": asset_id,
                        "managed": True,
                        "deploymentPlatformId":
                            "linux",
                    },
                }
            ),
        )

        result = adapter.execute(
            self._operation(),
            self._change(),
            "worker-1",
        )

        self.assertFalse(result.ok)

        self.assertEqual(
            [step.step_id for step in result.steps],
            [
                "resolve-release",
                "transfer-bootstrap",
                "transfer-runtime",
            ],
        )

        self.assertIn(
            "Operation cancellation requested",
            result.error or "",
        )


    def test_change_approver_is_authoritative_over_queue_confirmer(self):
        adapter, _, preflight, _ = self._adapter()

        operation = self._operation(
            confirmed_by="queue-operator"
        )
        change = self._change(
            approved_by="security-approver"
        )

        result = adapter.execute(
            operation,
            change,
            "worker-1",
        )

        self.assertTrue(result.ok)

        request = preflight.verify.call_args.args[0]

        self.assertEqual(
            request.approved_by,
            "security-approver",
        )
        self.assertNotEqual(
            operation["confirmed_by"],
            request.approved_by,
        )

    def test_missing_change_approver_fails_before_preflight(self):
        adapter, checkpoints, preflight, _ = self._adapter()

        with self.assertRaisesRegex(
            BlockchainChangeExecutionAdapterError,
            "missing approved_by",
        ):
            adapter.execute(
                self._operation(),
                self._change(approved_by=""),
                "worker-1",
            )

        self.assertEqual(checkpoints, [])
        preflight.verify.assert_not_called()

    def test_change_operation_binding_mismatch_fails_closed(self):
        adapter, checkpoints, preflight, _ = self._adapter()

        with self.assertRaisesRegex(
            BlockchainChangeExecutionAdapterError,
            "does not match operation",
        ):
            adapter.execute(
                self._operation(),
                self._change(
                    operation_id="different-operation"
                ),
                "worker-1",
            )

        self.assertEqual(checkpoints, [])
        preflight.verify.assert_not_called()

    def test_change_capability_binding_mismatch_fails_closed(self):
        adapter, checkpoints, preflight, _ = self._adapter()

        with self.assertRaisesRegex(
            BlockchainChangeExecutionAdapterError,
            "capability does not match operation",
        ):
            adapter.execute(
                self._operation(),
                self._change(
                    capability="linux.service.restart"
                ),
                "worker-1",
            )

        self.assertEqual(checkpoints, [])
        preflight.verify.assert_not_called()

    def test_change_must_require_approval(self):
        adapter, checkpoints, preflight, _ = self._adapter()

        with self.assertRaisesRegex(
            BlockchainChangeExecutionAdapterError,
            "must require approval",
        ):
            adapter.execute(
                self._operation(),
                self._change(
                    approval_required=False
                ),
                "worker-1",
            )

        self.assertEqual(checkpoints, [])
        preflight.verify.assert_not_called()

    def test_change_must_be_executing(self):
        adapter, checkpoints, preflight, _ = self._adapter()

        with self.assertRaisesRegex(
            BlockchainChangeExecutionAdapterError,
            "change is not executing",
        ):
            adapter.execute(
                self._operation(),
                self._change(status="approved"),
                "worker-1",
            )

        self.assertEqual(checkpoints, [])
        preflight.verify.assert_not_called()


    def test_typed_cancellation_propagates_from_durable_checkpoint(self):
        calls = 0

        def checkpoint(
            operation_id,
            worker_id,
            current_step,
            total_steps,
            lease_seconds,
        ):
            nonlocal calls
            del operation_id
            del worker_id
            del current_step
            del total_steps
            del lease_seconds

            calls += 1

            # Call 1 is the preflight Operations gate.
            # Call 2 is the resolve-release durable gate.
            if calls == 2:
                raise OperationCancellationRequested(
                    "Operation cancellation requested"
                )

        preflight = MagicMock()
        preflight.verify.return_value = object()

        assembly = MagicMock()

        def assemble(
            *,
            request,
            preflight,
            execution_control,
        ):
            del request
            del preflight
            return self._executor(
                execution_control
            )

        assembly.assemble.side_effect = assemble

        adapter = BlockchainChangeExecutionAdapter(
            preflight_service=preflight,
            assembly_service=assembly,
            checkpoint=checkpoint,
            platform_asset_loader=(
                lambda asset_id: {
                    "status": "ok",
                    "asset": {
                        "id": asset_id,
                        "managed": True,
                        "deploymentPlatformId":
                            "linux",
                    },
                }
            ),
        )

        with self.assertRaisesRegex(
            OperationCancellationRequested,
            "cancellation requested",
        ):
            adapter.execute(
                self._operation(),
                self._change(),
                "worker-1",
            )

        self.assertEqual(calls, 2)
        preflight.verify.assert_called_once()
        assembly.assemble.assert_called_once()

    def test_typed_lease_loss_propagates_from_durable_checkpoint(self):
        calls = 0

        def checkpoint(
            operation_id,
            worker_id,
            current_step,
            total_steps,
            lease_seconds,
        ):
            nonlocal calls
            del operation_id
            del worker_id
            del current_step
            del total_steps
            del lease_seconds

            calls += 1

            if calls == 2:
                raise OperationLeaseLost(
                    "Operation lease ownership was lost"
                )

        preflight = MagicMock()
        preflight.verify.return_value = object()

        assembly = MagicMock()

        def assemble(
            *,
            request,
            preflight,
            execution_control,
        ):
            del request
            del preflight
            return self._executor(
                execution_control
            )

        assembly.assemble.side_effect = assemble

        adapter = BlockchainChangeExecutionAdapter(
            preflight_service=preflight,
            assembly_service=assembly,
            checkpoint=checkpoint,
            platform_asset_loader=(
                lambda asset_id: {
                    "status": "ok",
                    "asset": {
                        "id": asset_id,
                        "managed": True,
                        "deploymentPlatformId":
                            "linux",
                    },
                }
            ),
        )

        with self.assertRaisesRegex(
            OperationLeaseLost,
            "lease ownership was lost",
        ):
            adapter.execute(
                self._operation(),
                self._change(),
                "worker-1",
            )

        self.assertEqual(calls, 2)
        preflight.verify.assert_called_once()
        assembly.assemble.assert_called_once()

    def test_umbrel_executes_through_manager_without_ssh_pipeline(
        self,
    ):
        from backend.services.blockchain_manager_install_execution_service import (
            BlockchainManagerInstallExecutionResult,
        )

        events = []
        manager_requests = []

        class ForbiddenPreflight:
            def verify(
                self,
                _request,
            ):
                raise AssertionError(
                    "Umbrel entered SSH preflight"
                )

        class ForbiddenAssembly:
            def assemble(
                self,
                *_args,
                **_kwargs,
            ):
                raise AssertionError(
                    "Umbrel entered SSH assembly"
                )

        class FakeManagerInstallService:
            def execute(
                self,
                request,
            ):
                events.append(
                    "manager"
                )

                manager_requests.append(
                    request
                )

                return (
                    BlockchainManagerInstallExecutionResult(
                        operation_id=(
                            "manager-operation-001"
                        ),
                        provider_id=(
                            request.provider_id
                        ),
                        storage_target_id=(
                            request.storage_target_id
                        ),
                        status="succeeded",
                        verified=True,
                        duration_ms=31,
                        evidence={
                            "targetAssetId": (
                                request.target_asset_id
                            ),
                            "authority": (
                                "blockchain-manager"
                            ),
                            "providerId": (
                                request.provider_id
                            ),
                            "storageTargetId": (
                                request.storage_target_id
                            ),
                            "managerOperationId": (
                                "manager-operation-001"
                            ),
                            "status":
                                "succeeded",
                            "verified":
                                True,
                            "durationMs":
                                31,
                        },
                    )
                )

        def checkpoint(
            operation_id,
            worker_id,
            step_number,
            total_steps,
            lease_seconds,
        ):
            self.assertTrue(
                operation_id
            )

            self.assertEqual(
                worker_id,
                "worker-1",
            )

            self.assertEqual(
                step_number,
                1,
            )

            self.assertGreaterEqual(
                total_steps,
                1,
            )

            self.assertGreater(
                lease_seconds,
                0,
            )

            events.append(
                "checkpoint"
            )

        adapter = (
            BlockchainChangeExecutionAdapter(
                preflight_service=(
                    ForbiddenPreflight()
                ),
                assembly_service=(
                    ForbiddenAssembly()
                ),
                checkpoint=checkpoint,
                platform_asset_loader=(
                    lambda asset_id: {
                        "status": "ok",
                        "asset": {
                            "id":
                                asset_id,
                            "managed":
                                True,
                            "deploymentPlatformId":
                                "umbrel",
                        },
                    }
                ),
                manager_install_service=(
                    FakeManagerInstallService()
                ),
            )
        )

        class FakeStorageService:
            def resolve(
                self,
                request,
            ):
                from backend.services.blockchain_deployment_storage_service import (
                    DeploymentStorageContext,
                )

                return DeploymentStorageContext(
                    storage_asset_id=(
                        request.storage_target_id
                    ),
                    storage_asset_type="storage",
                    target_asset_id=(
                        request.target_asset_id
                    ),
                    storage_source="/dev/sda6",
                    storage_filesystem="ext4",
                    storage_mount_path=(
                        "/private/not-public"
                    ),
                )

        original_storage_service = (
            __import__(
                "backend.services."
                "blockchain_change_execution_adapter",
                fromlist=[
                    "BlockchainDeploymentStorageService"
                ],
            ).BlockchainDeploymentStorageService
        )

        adapter_module = __import__(
            "backend.services."
            "blockchain_change_execution_adapter",
            fromlist=[
                "BlockchainDeploymentStorageService"
            ],
        )

        try:
            adapter_module.BlockchainDeploymentStorageService = (
                FakeStorageService
            )

            result = adapter.execute(
                self._operation(),
                self._change(),
                "worker-1",
            )
        finally:
            adapter_module.BlockchainDeploymentStorageService = (
                original_storage_service
            )

        self.assertEqual(
            events,
            [
                "checkpoint",
                "manager",
            ],
        )

        self.assertEqual(
            len(manager_requests),
            1,
        )

        manager_request = (
            manager_requests[0]
        )

        self.assertEqual(
            manager_request.target_asset_id,
            result.target_asset_id,
        )

        self.assertEqual(
            manager_request.provider_id,
            result.provider_id,
        )

        self.assertEqual(
            manager_request.storage_target_id,
            result.storage_target_id,
        )

        self.assertEqual(
            result.status,
            "completed",
        )

        self.assertTrue(
            result.ok
        )

        self.assertIsNone(
            result.error
        )

        self.assertEqual(
            result.duration_ms,
            31,
        )

        self.assertEqual(
            len(result.steps),
            1,
        )

        step = result.steps[0]

        self.assertEqual(
            step.step_id,
            "blockchain-manager-install",
        )

        self.assertEqual(
            step.status,
            "completed",
        )

        self.assertTrue(
            step.ok
        )

        self.assertEqual(
            step.evidence.get(
                "authority"
            ),
            "blockchain-manager",
        )

        rendered = repr(
            result.to_dict()
        )

        self.assertNotIn(
            "Bearer ",
            rendered,
        )

        self.assertNotIn(
            "control-token",
            rendered,
        )

        self.assertNotIn(
            "manager.test",
            rendered,
        )


if __name__ == "__main__":
    unittest.main()
