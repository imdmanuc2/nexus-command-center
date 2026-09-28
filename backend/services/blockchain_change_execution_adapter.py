from __future__ import annotations

from collections.abc import Callable
from typing import Any

from backend.capabilities.registry import (
    validate_blockchain_install_parameters,
)
from backend.db.repositories import (
    change_execution_repository as repo,
)
from backend.executors.blockchain_deployment_executor import (
    BlockchainDeploymentExecutor,
    DeploymentRequest,
    DeploymentResult,
    DeploymentStepResult,
)
from backend.services import cmdb_service
from backend.services.blockchain_manager_install_execution_service import (
    BlockchainManagerInstallExecutionRequest,
    BlockchainManagerInstallExecutionResult,
    BlockchainManagerInstallExecutionService,
)
from backend.services.blockchain_deployment_assembly_service import (
    BlockchainDeploymentAssemblyService,
)
from backend.services.blockchain_deployment_preflight_service import (
    BlockchainDeploymentPreflightService,
)
from backend.services.blockchain_deployment_storage_service import (
    BlockchainDeploymentStorageService,
)


class BlockchainChangeExecutionAdapterError(RuntimeError):
    pass


class BlockchainChangeExecutionAdapter:
    ACTION_ID = "blockchain.install"

    def __init__(
        self,
        *,
        preflight_service: (
            BlockchainDeploymentPreflightService | None
        ) = None,
        assembly_service: (
            BlockchainDeploymentAssemblyService | None
        ) = None,
        checkpoint: Callable[
            [str, str, int, int, int],
            Any,
        ] = repo.checkpoint_operation,
        lease_seconds: int = 120,
        platform_asset_loader: Callable[[str], object] = cmdb_service.get_asset,
        manager_install_service: BlockchainManagerInstallExecutionService | None = None,
    ) -> None:
        self._preflight_service = (
            preflight_service
            or BlockchainDeploymentPreflightService()
        )
        self._assembly_service = (
            assembly_service
            or BlockchainDeploymentAssemblyService()
        )
        self._checkpoint = checkpoint
        self._lease_seconds = int(lease_seconds)

        if self._lease_seconds < 1:
            raise ValueError(
                "lease_seconds must be positive"
            )
        self._platform_asset_loader = platform_asset_loader
        self._manager_install_service = (
            manager_install_service
            or BlockchainManagerInstallExecutionService()
        )

    @staticmethod
    def _required_text(
        value: Any,
        name: str,
    ) -> str:
        text = str(value or "").strip()

        if not text:
            raise BlockchainChangeExecutionAdapterError(
                f"Blockchain operation is missing {name}"
            )

        return text

    def _request_from_operation(
        self,
        operation: dict[str, Any],
        change: dict[str, Any],
    ) -> DeploymentRequest:
        if not isinstance(operation, dict):
            raise BlockchainChangeExecutionAdapterError(
                "Blockchain operation must be an object"
            )

        action_name = self._required_text(
            operation.get("action_name"),
            "action_name",
        )

        if action_name != self.ACTION_ID:
            raise BlockchainChangeExecutionAdapterError(
                "Operation is not blockchain.install"
            )

        if not bool(operation.get("confirmed")):
            raise BlockchainChangeExecutionAdapterError(
                "Blockchain installation requires confirmed approval"
            )

        # Queue confirmation authorizes this Operations execution,
        # but the durable Change Management approval is authoritative
        # for deployment approval provenance.
        self._required_text(
            operation.get("confirmed_by"),
            "confirmed_by",
        )

        if not isinstance(change, dict):
            raise BlockchainChangeExecutionAdapterError(
                "Blockchain installation requires an approved change"
            )

        if str(change.get("status") or "").strip() != "executing":
            raise BlockchainChangeExecutionAdapterError(
                "Blockchain installation change is not executing"
            )

        if not bool(change.get("approval_required")):
            raise BlockchainChangeExecutionAdapterError(
                "Blockchain installation change must require approval"
            )

        approved_by = self._required_text(
            change.get("approved_by"),
            "approved_by",
        )

        if change.get("operation_id") != operation.get("operation_id"):
            raise BlockchainChangeExecutionAdapterError(
                "Blockchain change does not match operation"
            )

        if change.get("capability") != self.ACTION_ID:
            raise BlockchainChangeExecutionAdapterError(
                "Blockchain change capability does not match operation"
            )

        correlation_id = self._required_text(
            operation.get("correlation_id"),
            "correlation_id",
        )

        target_type = self._required_text(
            operation.get("target_type"),
            "target_type",
        )

        if target_type != "asset":
            raise BlockchainChangeExecutionAdapterError(
                "Blockchain installation target must be an asset"
            )

        asset_id = self._required_text(
            operation.get("asset_id"),
            "asset_id",
        )

        target_id = str(
            operation.get("target_id") or ""
        ).strip()

        if target_id and target_id != asset_id:
            raise BlockchainChangeExecutionAdapterError(
                "Operation target does not match asset"
            )

        input_data = operation.get("input_data") or {}

        if not isinstance(input_data, dict):
            raise BlockchainChangeExecutionAdapterError(
                "Operation input_data must be an object"
            )

        parameters = input_data.get("parameters") or {}

        if not isinstance(parameters, dict):
            raise BlockchainChangeExecutionAdapterError(
                "Operation parameters must be an object"
            )

        validate_blockchain_install_parameters(
            parameters
        )

        provider_id = self._required_text(
            parameters.get("providerId"),
            "providerId",
        )

        storage_target_id = self._required_text(
            parameters.get("storageTargetId"),
            "storageTargetId",
        )

        return DeploymentRequest(
            provider_id=provider_id,
            storage_target_id=storage_target_id,
            target_asset_id=asset_id,
            correlation_id=correlation_id,
            approved_by=approved_by,
        )

    def _deployment_platform(
        self,
        *,
        target_asset_id: str,
    ) -> str:
        response = self._platform_asset_loader(
            target_asset_id
        )

        if not isinstance(response, dict):
            raise ValueError(
                "CMDB returned invalid deployment platform response"
            )

        if str(
            response.get("status") or ""
        ).strip().lower() != "ok":
            raise ValueError(
                "Deployment target does not exist in CMDB"
            )

        asset = response.get("asset")

        if not isinstance(asset, dict):
            raise ValueError(
                "CMDB returned invalid deployment target asset"
            )

        canonical_id = str(
            asset.get("id") or ""
        ).strip()

        if (
            not canonical_id
            or canonical_id != target_asset_id
        ):
            raise ValueError(
                "Deployment target CMDB identity mismatch"
            )

        if asset.get("managed") is not True:
            raise ValueError(
                "Deployment target is not Nexus-managed"
            )

        platform_id = str(
            asset.get("deploymentPlatformId")
            or ""
        ).strip().lower()

        if not platform_id:
            raise ValueError(
                "Deployment target has no explicit deployment platform"
            )

        return platform_id

    @staticmethod
    def _manager_step(
        result: BlockchainManagerInstallExecutionResult,
    ) -> DeploymentStepResult:
        if not isinstance(
            result,
            BlockchainManagerInstallExecutionResult,
        ):
            raise ValueError(
                "Blockchain Manager execution returned invalid result"
            )

        if (
            result.status != "succeeded"
            or result.verified is not True
        ):
            raise ValueError(
                "Blockchain Manager execution did not return verified success"
            )

        return DeploymentStepResult(
            step_id="blockchain-manager-install",
            status="completed",
            duration_ms=int(result.duration_ms),
            evidence=dict(result.evidence),
        )

    def execute(
        self,
        operation: dict[str, Any],
        change: dict[str, Any],
        worker_id: str,
    ) -> DeploymentResult:
        worker_id = self._required_text(
            worker_id,
            "worker_id",
        )

        operation_id = self._required_text(
            operation.get("operation_id")
            if isinstance(operation, dict)
            else None,
            "operation_id",
        )

        request = self._request_from_operation(
            operation,
            change,
        )

        total_steps = len(
            BlockchainDeploymentExecutor.STEP_IDS
        )

        # Preflight is outside the seven durable deployment
        # steps, but the Operations lease and cancellation
        # gate must still be valid before any target access.
        self._checkpoint(
            operation_id,
            worker_id,
            1,
            total_steps,
            self._lease_seconds,
        )

        platform_id = self._deployment_platform(
            target_asset_id=request.target_asset_id,
        )

        if platform_id == "umbrel":
            storage_context = (
                BlockchainDeploymentStorageService().resolve(
                    request
                )
            )

            if (
                storage_context.storage_asset_id
                != request.storage_target_id
            ):
                raise BlockchainChangeExecutionAdapterError(
                    "Deployment storage CMDB identity changed"
                )

            if (
                storage_context.target_asset_id
                != request.target_asset_id
            ):
                raise BlockchainChangeExecutionAdapterError(
                    "Deployment storage target identity changed"
                )

            manager_result = (
                self._manager_install_service.execute(
                    BlockchainManagerInstallExecutionRequest(
                        target_asset_id=request.target_asset_id,
                        provider_id=request.provider_id,
                        storage_target_id=request.storage_target_id,
                        storage_source=(
                            storage_context.storage_source
                        ),
                        storage_filesystem=(
                            storage_context.storage_filesystem
                        ),
                    )
                )
            )

            manager_step = self._manager_step(
                manager_result
            )

            return DeploymentResult(
                status="completed",
                provider_id=request.provider_id,
                storage_target_id=request.storage_target_id,
                target_asset_id=request.target_asset_id,
                correlation_id=request.correlation_id,
                approved_by=request.approved_by,
                duration_ms=int(
                    manager_result.duration_ms
                ),
                steps=(manager_step,),
                error=None,
            )

        preflight = self._preflight_service.verify(
            request
        )

        def execution_control(
            control_request: DeploymentRequest,
            step_id: str,
            step_number: int,
            control_total_steps: int,
        ) -> None:
            if control_request != request:
                raise BlockchainChangeExecutionAdapterError(
                    "Deployment control request changed"
                )

            expected_step = (
                BlockchainDeploymentExecutor
                .STEP_IDS[step_number - 1]
            )

            if step_id != expected_step:
                raise BlockchainChangeExecutionAdapterError(
                    "Deployment durable step identity changed"
                )

            if control_total_steps != total_steps:
                raise BlockchainChangeExecutionAdapterError(
                    "Deployment durable step count changed"
                )

            self._checkpoint(
                operation_id,
                worker_id,
                step_number,
                total_steps,
                self._lease_seconds,
            )

        executor = self._assembly_service.assemble(
            request=request,
            preflight=preflight,
            execution_control=execution_control,
        )

        if not isinstance(
            executor,
            BlockchainDeploymentExecutor,
        ):
            raise BlockchainChangeExecutionAdapterError(
                "Deployment assembler returned invalid executor"
            )

        result = executor.execute(request)

        if not isinstance(
            result,
            DeploymentResult,
        ):
            raise BlockchainChangeExecutionAdapterError(
                "Deployment executor returned invalid result"
            )

        return result
