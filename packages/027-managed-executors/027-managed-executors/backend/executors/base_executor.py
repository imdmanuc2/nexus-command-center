from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backend.executors.results import ExecutionResult


class BaseExecutor(ABC):
    name = "base"

    @abstractmethod
    def supports(self, action_id: str, run: dict[str, Any]) -> bool:
        raise NotImplementedError

    def validate(self, run: dict[str, Any]) -> None:
        if not str(run.get("actionId") or "").strip():
            raise ValueError("Executor request is missing actionId")
        if not str(run.get("entityType") or "").strip():
            raise ValueError("Executor request is missing entityType")
        if not str(run.get("entityId") or "").strip():
            raise ValueError("Executor request is missing entityId")

    @abstractmethod
    def execute(self, run: dict[str, Any]) -> ExecutionResult:
        raise NotImplementedError

    def rollback(self, run: dict[str, Any]) -> ExecutionResult:
        return ExecutionResult(
            status="not-supported",
            executor=self.name,
            action=str(run.get("actionId") or "unknown"),
            entity_type=str(run.get("entityType") or "unknown"),
            entity_id=str(run.get("entityId") or "unknown"),
            summary="This executor does not provide automatic rollback.",
            safe_noop=True,
        )
