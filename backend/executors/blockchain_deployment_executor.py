from __future__ import annotations

import copy
import json
import time
from dataclasses import asdict, dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Mapping

from backend.core.operation_execution_control import (
    OperationCancellationRequested,
    OperationLeaseLost,
)



@dataclass(frozen=True, slots=True)
class DeploymentRequest:
    provider_id: str
    storage_target_id: str
    target_asset_id: str
    correlation_id: str
    approved_by: str


@dataclass(frozen=True, slots=True)
class DeploymentStepOutput:
    evidence: dict[str, Any] = field(default_factory=dict)
    private: Any = None


@dataclass(frozen=True, slots=True)
class DeploymentStepResult:
    step_id: str
    status: str
    duration_ms: int
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "completed"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return {
            "stepId": payload["step_id"],
            "status": payload["status"],
            "durationMs": payload["duration_ms"],
            "evidence": payload["evidence"],
        }


@dataclass(frozen=True, slots=True)
class DeploymentResult:
    status: str
    provider_id: str
    storage_target_id: str
    target_asset_id: str
    correlation_id: str
    approved_by: str
    duration_ms: int
    steps: tuple[DeploymentStepResult, ...]
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "completed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "providerId": self.provider_id,
            "storageTargetId": self.storage_target_id,
            "targetAssetId": self.target_asset_id,
            "correlationId": self.correlation_id,
            "approvedBy": self.approved_by,
            "durationMs": self.duration_ms,
            "steps": [step.to_dict() for step in self.steps],
            "error": self.error,
        }


class BlockchainDeploymentError(RuntimeError):
    pass


class BlockchainDeploymentExecutor:
    """
    Provider-neutral blockchain deployment orchestrator.

    This foundation deliberately has no SSH, SCP, shell, transport,
    provider catalog, filesystem, or standalone Blockchain Manager
    dependency. Concrete reviewed deployment primitives are injected
    later.

    A failed required step terminates execution immediately.
    """

    STEP_IDS = (
        "resolve-release",
        "transfer-bootstrap",
        "transfer-runtime",
        "invoke-bootstrap",
        "verify-runtime",
        "invoke-installer",
        "verify-installation",
    )

    def __init__(
        self,
        *,
        resolve_release: Callable[
            [DeploymentRequest],
            DeploymentStepOutput | dict[str, Any],
        ],
        transfer_bootstrap: Callable[
            [
                DeploymentRequest,
                dict[str, Any],
                Mapping[str, Any],
            ],
            DeploymentStepOutput | dict[str, Any],
        ],
        transfer_runtime: Callable[
            [
                DeploymentRequest,
                dict[str, Any],
                Mapping[str, Any],
            ],
            DeploymentStepOutput | dict[str, Any],
        ],
        invoke_bootstrap: Callable[
            [
                DeploymentRequest,
                dict[str, Any],
                Mapping[str, Any],
            ],
            DeploymentStepOutput | dict[str, Any],
        ],
        verify_runtime: Callable[
            [
                DeploymentRequest,
                dict[str, Any],
                Mapping[str, Any],
            ],
            DeploymentStepOutput | dict[str, Any],
        ],
        invoke_installer: Callable[
            [
                DeploymentRequest,
                dict[str, Any],
                Mapping[str, Any],
            ],
            DeploymentStepOutput | dict[str, Any],
        ],
        verify_installation: Callable[
            [
                DeploymentRequest,
                dict[str, Any],
                Mapping[str, Any],
            ],
            DeploymentStepOutput | dict[str, Any],
        ],
        execution_control: Callable[
            [DeploymentRequest, str, int, int],
            None,
        ]
        | None = None,
    ) -> None:
        self._execution_control = execution_control
        self._steps = (
            ("resolve-release", resolve_release),
            ("transfer-bootstrap", transfer_bootstrap),
            ("transfer-runtime", transfer_runtime),
            ("invoke-bootstrap", invoke_bootstrap),
            ("verify-runtime", verify_runtime),
            ("invoke-installer", invoke_installer),
            ("verify-installation", verify_installation),
        )

    @staticmethod
    def _validate_request(request: DeploymentRequest) -> None:
        required = {
            "provider_id": request.provider_id,
            "storage_target_id": request.storage_target_id,
            "target_asset_id": request.target_asset_id,
            "correlation_id": request.correlation_id,
            "approved_by": request.approved_by,
        }

        for name, value in required.items():
            if not str(value or "").strip():
                raise BlockchainDeploymentError(
                    f"Deployment request is missing {name}"
                )

    @staticmethod
    def _normalize_output(
        step_id: str,
        value: DeploymentStepOutput | dict[str, Any],
    ) -> DeploymentStepOutput:
        if isinstance(value, dict):
            output = DeploymentStepOutput(evidence=value)
        elif isinstance(value, DeploymentStepOutput):
            output = value
        else:
            raise BlockchainDeploymentError(
                f"{step_id} returned invalid evidence"
            )

        if not isinstance(output.evidence, dict):
            raise BlockchainDeploymentError(
                f"{step_id} returned invalid evidence"
            )

        try:
            json.dumps(
                output.evidence,
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise BlockchainDeploymentError(
                f"{step_id} returned non-JSON-safe evidence"
            ) from exc

        return output

    def execute(self, request: DeploymentRequest) -> DeploymentResult:
        self._validate_request(request)

        started = time.perf_counter()
        steps: list[DeploymentStepResult] = []
        context: dict[str, Any] = {}
        private_context: dict[str, Any] = {}

        total_steps = len(self._steps)

        for step_number, (step_id, handler) in enumerate(
            self._steps,
            start=1,
        ):
            step_started = time.perf_counter()

            try:
                if self._execution_control is not None:
                    self._execution_control(
                        request,
                        step_id,
                        step_number,
                        total_steps,
                    )

                if step_id == "resolve-release":
                    raw_output = handler(request)
                else:
                    raw_output = handler(
                        request,
                        copy.deepcopy(context),
                        MappingProxyType(
                            dict(private_context)
                        ),
                    )

                output = self._normalize_output(
                    step_id,
                    raw_output,
                )
                evidence = output.evidence

                step = DeploymentStepResult(
                    step_id=step_id,
                    status="completed",
                    duration_ms=round(
                        (time.perf_counter() - step_started) * 1000
                    ),
                    evidence=copy.deepcopy(evidence),
                )
                steps.append(step)
                context[step_id] = copy.deepcopy(evidence)

                if output.private is not None:
                    private_context[step_id] = output.private

            except (
                OperationCancellationRequested,
                OperationLeaseLost,
            ):
                raise
            except Exception as exc:
                step = DeploymentStepResult(
                    step_id=step_id,
                    status="failed",
                    duration_ms=round(
                        (time.perf_counter() - step_started) * 1000
                    ),
                    evidence={},
                )
                steps.append(step)

                return DeploymentResult(
                    status="failed",
                    provider_id=request.provider_id,
                    storage_target_id=request.storage_target_id,
                    target_asset_id=request.target_asset_id,
                    correlation_id=request.correlation_id,
                    approved_by=request.approved_by,
                    duration_ms=round(
                        (time.perf_counter() - started) * 1000
                    ),
                    steps=tuple(steps),
                    error=f"{step_id}: {exc}",
                )

        return DeploymentResult(
            status="completed",
            provider_id=request.provider_id,
            storage_target_id=request.storage_target_id,
            target_asset_id=request.target_asset_id,
            correlation_id=request.correlation_id,
            approved_by=request.approved_by,
            duration_ms=round(
                (time.perf_counter() - started) * 1000
            ),
            steps=tuple(steps),
            error=None,
        )
