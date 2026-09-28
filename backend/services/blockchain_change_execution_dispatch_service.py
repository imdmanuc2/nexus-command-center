from __future__ import annotations

from typing import Any, Callable

from backend.executors.blockchain_deployment_executor import (
    DeploymentResult,
)


class BlockchainChangeExecutionDispatchError(RuntimeError):
    pass


class BlockchainChangeExecutionDispatchService:
    """
    Offline Operations dispatch boundary for blockchain.install.

    This service deliberately does not register itself with the normal
    change execution worker and does not make blockchain.install
    executable through CapabilityDefinition.build_argv().
    """

    ACTION_NAME = "blockchain.install"

    def __init__(
        self,
        *,
        adapter_factory: Callable[[], Any],
    ) -> None:
        if not callable(adapter_factory):
            raise TypeError("adapter_factory must be callable")
        self._adapter_factory = adapter_factory

    @staticmethod
    def _required_text(
        value: Any,
        name: str,
    ) -> str:
        text = str(value or "").strip()
        if not text:
            raise BlockchainChangeExecutionDispatchError(
                f"{name} is required"
            )
        return text

    def execute(
        self,
        operation: dict[str, Any],
        change: dict[str, Any],
        worker_id: str,
    ) -> DeploymentResult:
        if not isinstance(operation, dict):
            raise BlockchainChangeExecutionDispatchError(
                "operation must be an object"
            )

        action_name = self._required_text(
            operation.get("action_name"),
            "action_name",
        )

        if action_name != self.ACTION_NAME:
            raise BlockchainChangeExecutionDispatchError(
                "Unsupported specialized operation action"
            )

        worker_id = self._required_text(
            worker_id,
            "worker_id",
        )

        adapter = self._adapter_factory()

        execute = getattr(adapter, "execute", None)
        if not callable(execute):
            raise BlockchainChangeExecutionDispatchError(
                "Blockchain execution adapter is invalid"
            )

        result = execute(
            operation,
            change,
            worker_id,
        )

        if not isinstance(result, DeploymentResult):
            raise BlockchainChangeExecutionDispatchError(
                "Blockchain execution adapter returned invalid result"
            )

        return result

    @staticmethod
    def result_data(
        result: DeploymentResult,
    ) -> dict[str, Any]:
        if not isinstance(result, DeploymentResult):
            raise BlockchainChangeExecutionDispatchError(
                "Deployment result is invalid"
            )

        payload = result.to_dict()

        if not isinstance(payload, dict):
            raise BlockchainChangeExecutionDispatchError(
                "Deployment result payload is invalid"
            )

        if payload.get("status") != result.status:
            raise BlockchainChangeExecutionDispatchError(
                "Deployment result status changed during projection"
            )

        steps = payload.get("steps")

        if not isinstance(steps, list):
            raise BlockchainChangeExecutionDispatchError(
                "Deployment result steps are invalid"
            )

        return payload
