from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from backend.core.operation_execution_control import (
    OperationCancellationRequested,
    OperationLeaseLost,
)
from backend.executors.blockchain_deployment_executor import (
    BlockchainDeploymentExecutor,
    DeploymentRequest,
    DeploymentStepOutput,
)
from backend.services.blockchain_deployment_target_service import (
    DeploymentTargetContext,
)
from backend.services.blockchain_target_platform import (
    UMBREL_TARGET_PROFILE,
)
from backend.transports.models import (
    TransportTarget,
)
from backend.transports.target_prerequisites import (
    TargetPrerequisiteResult,
)
from backend.services import change_execution_service as worker
from backend.services.blockchain_change_execution_adapter import (
    BlockchainChangeExecutionAdapter,
)
from backend.services.blockchain_change_execution_dispatch_service import (
    BlockchainChangeExecutionDispatchService,
)

from backend.services.blockchain_deployment_preflight_service import (
    BlockchainDeploymentPreflightService,
)
from backend.services.blockchain_deployment_storage_service import (
    BlockchainDeploymentStorageService,
)


class _OfflineTargetService:
    def __init__(self):
        self.calls = []

        self.target = TransportTarget(
            asset_id="asset-managed-1",
            transport="ssh",
            host="192.0.2.10",
            port=22,
            username="umbrel",
            identity_file="/private/identity",
            known_hosts_file="/private/known_hosts",
        )

    def resolve(self, request):
        self.calls.append(request)

        return DeploymentStepOutput(
            evidence={
                "targetAssetId":
                    request.target_asset_id,
                "transport": "ssh",
                "deploymentPlatformId":
                    UMBREL_TARGET_PROFILE.platform_id,
            },
            private=DeploymentTargetContext(
                target=self.target,
                profile=UMBREL_TARGET_PROFILE,
            ),
        )


class _OfflinePreflight:
    def __init__(self):
        self.calls = []

    def verify(self, request):
        self.calls.append(request)
        return object()


class _OfflineAssembly:
    def __init__(
        self,
        *,
        fail_step: str | None = None,
    ):
        self.fail_step = fail_step
        self.calls = []

    def _step(
        self,
        step_id,
        request,
        *_args,
    ):
        if self.fail_step == step_id:
            raise RuntimeError(
                f"{step_id} offline failure"
            )

        return DeploymentStepOutput(
            evidence={
                "stepId": step_id,
                "mode": "offline",
            }
        )

    def assemble(
        self,
        *,
        request,
        preflight,
        execution_control,
    ):
        self.calls.append(
            {
                "request": request,
                "preflight": preflight,
                "execution_control":
                    execution_control,
            }
        )

        return BlockchainDeploymentExecutor(
            resolve_release=lambda req:
                self._step(
                    "resolve-release",
                    req,
                ),
            transfer_bootstrap=lambda req, ctx, private:
                self._step(
                    "transfer-bootstrap",
                    req,
                    ctx,
                    private,
                ),
            transfer_runtime=lambda req, ctx, private:
                self._step(
                    "transfer-runtime",
                    req,
                    ctx,
                    private,
                ),
            invoke_bootstrap=lambda req, ctx, private:
                self._step(
                    "invoke-bootstrap",
                    req,
                    ctx,
                    private,
                ),
            verify_runtime=lambda req, ctx, private:
                self._step(
                    "verify-runtime",
                    req,
                    ctx,
                    private,
                ),
            invoke_installer=lambda req, ctx, private:
                self._step(
                    "invoke-installer",
                    req,
                    ctx,
                    private,
                ),
            verify_installation=lambda req, ctx, private:
                self._step(
                    "verify-installation",
                    req,
                    ctx,
                    private,
                ),
            execution_control=execution_control,
        )


class BlockchainOperationsOfflineIntegrationTests(
    unittest.TestCase
):
    def operation(self):
        return {
            "operation_id": "op-offline-1",
            "action_name": "blockchain.install",
            "target_type": "asset",
            "target_id": "asset-managed-1",
            "asset_id": "asset-managed-1",
            "correlation_id": "corr-offline-1",
            "confirmed": True,
            "confirmed_by": "queue-operator",
            "input_data": {
                "parameters": {
                    "providerId":
                        "bitcoin-mainnet",
                    "storageTargetId":
                        "storage-main",
                }
            },
        }

    def change(self):
        return {
            "change_id": "change-offline-1",
            "operation_id": "op-offline-1",
            "status": "executing",
            "approval_required": True,
            "approved_by": "change-approver",
            "capability": "blockchain.install",
        }

    def dispatch(
        self,
        *,
        checkpoint,
        fail_step=None,
    ):
        preflight = _OfflinePreflight()
        assembly = _OfflineAssembly(
            fail_step=fail_step
        )

        def adapter_factory():
            return BlockchainChangeExecutionAdapter(
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

        dispatch = (
            BlockchainChangeExecutionDispatchService(
                adapter_factory=adapter_factory,
            )
        )

        return dispatch, preflight, assembly

    def test_success_full_offline_operations_path(
        self,
    ):
        operation = self.operation()
        change = self.change()
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
                "lease_owner": worker_id,
            }

        dispatch, preflight, assembly = (
            self.dispatch(
                checkpoint=checkpoint
            )
        )

        with (
            patch.object(
                worker.repo,
                "find_change_for_operation",
                return_value=change,
            ),
            patch.object(
                worker.repo,
                "start_attempt",
                return_value="attempt-offline-1",
            ),
            patch.object(
                worker,
                "_blockchain_install_dispatch",
                return_value=dispatch,
            ),
            patch.object(
                worker.repo,
                "finish_success",
            ) as finish_success,
            patch.object(
                worker.repo,
                "finish_failure",
            ) as finish_failure,
            patch.object(
                worker.repo,
                "finish_cancelled",
            ) as finish_cancelled,
            patch.object(
                worker,
                "get_capability_registry",
            ) as generic_registry,
        ):
            result = worker.execute_operation(
                operation,
                "worker-offline-1",
            )

        self.assertEqual(
            result["status"],
            "succeeded",
        )

        generic_registry.assert_not_called()
        finish_failure.assert_not_called()
        finish_cancelled.assert_not_called()
        finish_success.assert_called_once()

        self.assertEqual(
            len(preflight.calls),
            1,
        )

        request = preflight.calls[0]

        self.assertEqual(
            request,
            DeploymentRequest(
                provider_id="bitcoin-mainnet",
                storage_target_id="storage-main",
                target_asset_id="asset-managed-1",
                correlation_id="corr-offline-1",
                approved_by="change-approver",
            ),
        )

        self.assertEqual(
            len(assembly.calls),
            1,
        )

        self.assertEqual(
            len(checkpoints),
            8,
        )

        self.assertEqual(
            checkpoints[0],
            (
                "op-offline-1",
                "worker-offline-1",
                1,
                7,
                120,
            ),
        )

        self.assertEqual(
            [item[2] for item in checkpoints[1:]],
            list(range(1, 8)),
        )

        persisted = (
            finish_success.call_args.args[3]
        )

        self.assertEqual(
            persisted["status"],
            "completed",
        )

        self.assertEqual(
            len(persisted["steps"]),
            7,
        )

        self.assertEqual(
            finish_success.call_args.args[-1],
            "worker-offline-1",
        )

    def test_offline_deployment_failure_finalizes_failure(
        self,
    ):
        operation = self.operation()
        change = self.change()

        def checkpoint(*_args):
            return {
                "status": "running"
            }

        dispatch, _, _ = self.dispatch(
            checkpoint=checkpoint,
            fail_step="verify-runtime",
        )

        with (
            patch.object(
                worker.repo,
                "find_change_for_operation",
                return_value=change,
            ),
            patch.object(
                worker.repo,
                "start_attempt",
                return_value="attempt-offline-1",
            ),
            patch.object(
                worker,
                "_blockchain_install_dispatch",
                return_value=dispatch,
            ),
            patch.object(
                worker.repo,
                "finish_success",
            ) as finish_success,
            patch.object(
                worker.repo,
                "finish_failure",
            ) as finish_failure,
            patch.object(
                worker.repo,
                "finish_cancelled",
            ) as finish_cancelled,
        ):
            result = worker.execute_operation(
                operation,
                "worker-offline-1",
            )

        self.assertEqual(
            result["status"],
            "failed",
        )

        finish_success.assert_not_called()
        finish_cancelled.assert_not_called()
        finish_failure.assert_called_once()

        payload = (
            finish_failure.call_args.args[4]
        )

        self.assertEqual(
            payload["status"],
            "failed",
        )

        self.assertIn(
            "verify-runtime offline failure",
            finish_failure.call_args.args[3],
        )

    def test_offline_cancellation_finalizes_cancelled(
        self,
    ):
        operation = self.operation()
        change = self.change()
        calls = 0

        def checkpoint(*_args):
            nonlocal calls
            calls += 1

            if calls == 3:
                raise OperationCancellationRequested(
                    "Operation cancellation requested"
                )

            return {
                "status": "running"
            }

        dispatch, _, _ = self.dispatch(
            checkpoint=checkpoint
        )

        with (
            patch.object(
                worker.repo,
                "find_change_for_operation",
                return_value=change,
            ),
            patch.object(
                worker.repo,
                "start_attempt",
                return_value="attempt-offline-1",
            ),
            patch.object(
                worker,
                "_blockchain_install_dispatch",
                return_value=dispatch,
            ),
            patch.object(
                worker.repo,
                "finish_success",
            ) as finish_success,
            patch.object(
                worker.repo,
                "finish_failure",
            ) as finish_failure,
            patch.object(
                worker.repo,
                "finish_cancelled",
            ) as finish_cancelled,
        ):
            result = worker.execute_operation(
                operation,
                "worker-offline-1",
            )

        self.assertEqual(
            result["status"],
            "cancelled",
        )

        finish_success.assert_not_called()
        finish_failure.assert_not_called()
        finish_cancelled.assert_called_once()

    def test_offline_lease_loss_never_finalizes(
        self,
    ):
        operation = self.operation()
        change = self.change()
        calls = 0

        def checkpoint(*_args):
            nonlocal calls
            calls += 1

            if calls == 2:
                raise OperationLeaseLost(
                    "Operation lease ownership was lost"
                )

            return {
                "status": "running"
            }

        dispatch, _, _ = self.dispatch(
            checkpoint=checkpoint
        )

        with (
            patch.object(
                worker.repo,
                "find_change_for_operation",
                return_value=change,
            ),
            patch.object(
                worker.repo,
                "start_attempt",
                return_value="attempt-offline-1",
            ),
            patch.object(
                worker,
                "_blockchain_install_dispatch",
                return_value=dispatch,
            ),
            patch.object(
                worker.repo,
                "finish_success",
            ) as finish_success,
            patch.object(
                worker.repo,
                "finish_failure",
            ) as finish_failure,
            patch.object(
                worker.repo,
                "finish_cancelled",
            ) as finish_cancelled,
        ):
            result = worker.execute_operation(
                operation,
                "worker-offline-1",
            )

        self.assertEqual(
            result["status"],
            "lease-lost",
        )

        finish_success.assert_not_called()
        finish_failure.assert_not_called()
        finish_cancelled.assert_not_called()


    def _storage_authority_dispatch(
        self,
        *,
        asset_getter,
        relationship_getter,
        prerequisite_transport,
        assembly_service,
    ):
        storage = BlockchainDeploymentStorageService(
            asset_getter=asset_getter,
            relationship_getter=relationship_getter,
        )

        preflight = BlockchainDeploymentPreflightService(
            target_service=_OfflineTargetService(),
            storage_service=storage,
            prerequisite_transport=prerequisite_transport,
        )

        def adapter_factory():
            return BlockchainChangeExecutionAdapter(
                preflight_service=preflight,
                assembly_service=assembly_service,
                checkpoint=lambda *_args: {
                    "status": "running",
                    "lease_owner":
                        "worker-storage-authority",
                },
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

        return BlockchainChangeExecutionDispatchService(
            adapter_factory=adapter_factory,
        )

    def test_missing_cmdb_storage_fails_before_ssh(
        self,
    ):
        operation = self.operation()
        change = self.change()

        asset_getter = MagicMock(
            return_value={
                "status": "not_found",
            }
        )

        relationship_getter = MagicMock()

        prerequisite_transport = MagicMock()
        assembly_service = MagicMock()

        dispatch = self._storage_authority_dispatch(
            asset_getter=asset_getter,
            relationship_getter=relationship_getter,
            prerequisite_transport=prerequisite_transport,
            assembly_service=assembly_service,
        )

        with (
            patch.object(
                worker.repo,
                "find_change_for_operation",
                return_value=change,
            ),
            patch.object(
                worker.repo,
                "start_attempt",
                return_value="attempt-storage-missing",
            ),
            patch.object(
                worker,
                "_blockchain_install_dispatch",
                return_value=dispatch,
            ),
            patch.object(
                worker.repo,
                "finish_success",
            ) as finish_success,
            patch.object(
                worker.repo,
                "finish_failure",
            ) as finish_failure,
            patch.object(
                worker.repo,
                "finish_cancelled",
            ) as finish_cancelled,
        ):
            result = worker.execute_operation(
                operation,
                "worker-storage-authority",
            )

        self.assertEqual(
            result["status"],
            "failed",
        )

        self.assertIn(
            "does not exist in CMDB",
            result.get("error", ""),
        )

        asset_getter.assert_called_once_with(
            "storage-main"
        )

        relationship_getter.assert_not_called()

        prerequisite_transport.verify.assert_not_called()
        assembly_service.assemble.assert_not_called()

        finish_success.assert_not_called()
        finish_cancelled.assert_not_called()
        finish_failure.assert_called_once()

    def test_unapproved_storage_mount_fails_before_ssh(
        self,
    ):
        operation = self.operation()
        change = self.change()

        asset_getter = MagicMock(
            return_value={
                "status": "ok",
                "asset": {
                    "id": "storage-main",
                    "assetType": "storage",
                    "managed": True,
                    "capabilities": [
                        "blockchain-storage",
                    ],
                },
            }
        )

        relationship_getter = MagicMock(
            return_value=[
                {
                    "sourceType": "asset",
                    "sourceId": "asset-managed-1",
                    "relationshipType": "mounts",
                    "targetType": "asset",
                    "targetId": "storage-main",
                    "status": "active",
                    "approved": False,
                }
            ]
        )

        prerequisite_transport = MagicMock()
        assembly_service = MagicMock()

        dispatch = self._storage_authority_dispatch(
            asset_getter=asset_getter,
            relationship_getter=relationship_getter,
            prerequisite_transport=prerequisite_transport,
            assembly_service=assembly_service,
        )

        with (
            patch.object(
                worker.repo,
                "find_change_for_operation",
                return_value=change,
            ),
            patch.object(
                worker.repo,
                "start_attempt",
                return_value="attempt-storage-unapproved",
            ),
            patch.object(
                worker,
                "_blockchain_install_dispatch",
                return_value=dispatch,
            ),
            patch.object(
                worker.repo,
                "finish_success",
            ) as finish_success,
            patch.object(
                worker.repo,
                "finish_failure",
            ) as finish_failure,
            patch.object(
                worker.repo,
                "finish_cancelled",
            ) as finish_cancelled,
        ):
            result = worker.execute_operation(
                operation,
                "worker-storage-authority",
            )

        self.assertEqual(
            result["status"],
            "failed",
        )

        self.assertIn(
            "not authorized",
            result.get("error", ""),
        )

        asset_getter.assert_called_once_with(
            "storage-main"
        )

        relationship_getter.assert_called_once()

        prerequisite_transport.verify.assert_not_called()
        assembly_service.assemble.assert_not_called()

        finish_success.assert_not_called()
        finish_cancelled.assert_not_called()
        finish_failure.assert_called_once()



    def test_authorized_storage_reaches_ssh_preflight_once(
        self,
    ):
        operation = self.operation()
        change = self.change()

        asset_getter = MagicMock(
            return_value={
                "status": "ok",
                "asset": {
                    "id": "storage-main",
                    "assetType": "storage",
                    "managed": True,
                    "capabilities": [
                        "blockchain-storage",
                    ],
                },
            }
        )

        relationship_getter = MagicMock(
            return_value=[
                {
                    "sourceType": "asset",
                    "sourceId": "asset-managed-1",
                    "relationshipType": "mounts",
                    "targetType": "asset",
                    "targetId": "storage-main",
                    "status": "active",
                    "approved": True,
                    "metadata": {
                        "mountPath":
                            "/private/cmdb/mount",
                        "filesystem":
                            "ext4",
                    },
                }
            ]
        )

        prerequisite_transport = MagicMock()

        prerequisite_transport.verify.return_value = (
            TargetPrerequisiteResult(
                platform_id="umbrel",
                python_version="Python 3.11.9",
                tar_version="tar (GNU tar) 1.34",
                checks=(
                    "runtime-parent-exists",
                    "runtime-parent-writable",
                    "staging-parent-exists",
                    "staging-parent-writable",
                    "python3-executable",
                    "tar-executable",
                    "sha256sum-executable",
                    "rm-executable",
                    "python-version",
                    "python-tar-filter",
                    "tar-version",
                ),
                duration_ms=12,
                host_key_verified=True,
            )
        )

        assembly_service = MagicMock()

        captured = {}

        def assemble(
            *,
            request,
            preflight,
            execution_control,
        ):
            captured["request"] = request
            captured["preflight"] = preflight
            captured[
                "execution_control"
            ] = execution_control

            return _OfflineAssembly().assemble(
                request=request,
                preflight=preflight,
                execution_control=(
                    execution_control
                ),
            )

        assembly_service.assemble.side_effect = (
            assemble
        )

        dispatch = self._storage_authority_dispatch(
            asset_getter=asset_getter,
            relationship_getter=relationship_getter,
            prerequisite_transport=(
                prerequisite_transport
            ),
            assembly_service=assembly_service,
        )

        with (
            patch.object(
                worker.repo,
                "find_change_for_operation",
                return_value=change,
            ),
            patch.object(
                worker.repo,
                "start_attempt",
                return_value=(
                    "attempt-storage-authorized"
                ),
            ),
            patch.object(
                worker,
                "_blockchain_install_dispatch",
                return_value=dispatch,
            ),
            patch.object(
                worker.repo,
                "finish_success",
            ) as finish_success,
            patch.object(
                worker.repo,
                "finish_failure",
            ) as finish_failure,
            patch.object(
                worker.repo,
                "finish_cancelled",
            ) as finish_cancelled,
        ):
            result = worker.execute_operation(
                operation,
                "worker-storage-authority",
            )

        self.assertEqual(
            result["status"],
            "succeeded",
        )

        asset_getter.assert_called_once_with(
            "storage-main"
        )

        relationship_getter.assert_called_once()

        prerequisite_transport.verify.assert_called_once()

        prerequisite_call = (
            prerequisite_transport
            .verify
            .call_args
        )

        self.assertEqual(
            prerequisite_call.kwargs[
                "target"
            ].asset_id,
            "asset-managed-1",
        )

        self.assertEqual(
            prerequisite_call.kwargs[
                "target"
            ].transport,
            "ssh",
        )

        self.assertIs(
            prerequisite_call.kwargs[
                "profile"
            ],
            UMBREL_TARGET_PROFILE,
        )

        self.assertEqual(
            prerequisite_call.kwargs[
                "timeout_seconds"
            ],
            30,
        )

        assembly_service.assemble.assert_called_once()

        preflight = captured[
            "preflight"
        ]

        self.assertEqual(
            preflight.context.storage.storage_asset_id,
            "storage-main",
        )

        self.assertEqual(
            preflight.context.storage.storage_asset_type,
            "storage",
        )

        self.assertEqual(
            preflight.context.storage.target_asset_id,
            "asset-managed-1",
        )

        self.assertEqual(
            preflight.evidence[
                "storageTargetId"
            ],
            "storage-main",
        )

        self.assertEqual(
            preflight.evidence[
                "storageAssetType"
            ],
            "storage",
        )

        public_projection = json.dumps({
            "request": {
                "providerId":
                    captured[
                        "request"
                    ].provider_id,
                "storageTargetId":
                    captured[
                        "request"
                    ].storage_target_id,
                "targetAssetId":
                    captured[
                        "request"
                    ].target_asset_id,
                "correlationId":
                    captured[
                        "request"
                    ].correlation_id,
                "approvedBy":
                    captured[
                        "request"
                    ].approved_by,
            },
            "preflightEvidence":
                preflight.evidence,
        })

        for forbidden in (
            "/private/cmdb/mount",
            "mountPath",
            "filesystem",
            "ext4",
            "/private/identity",
            "/private/known_hosts",
            "192.0.2.10",
        ):
            self.assertNotIn(
                forbidden,
                public_projection,
            )

        finish_success.assert_called_once()
        finish_failure.assert_not_called()
        finish_cancelled.assert_not_called()


if __name__ == "__main__":
    unittest.main()
