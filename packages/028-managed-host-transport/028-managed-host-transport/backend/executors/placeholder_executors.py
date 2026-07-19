from __future__ import annotations

from typing import Any

from backend.executors.base_executor import BaseExecutor
from backend.executors.results import ExecutionResult


class _PlaceholderExecutor(BaseExecutor):
    actions: set[str] = set()

    def supports(self, action_id: str, run: dict[str, Any]) -> bool:
        return action_id in self.actions

    def execute(self, run: dict[str, Any]) -> ExecutionResult:
        self.validate(run)
        return ExecutionResult(
            status="planned",
            executor=self.name,
            action=run["actionId"],
            entity_type=run["entityType"],
            entity_id=run["entityId"],
            summary=(
                f"The {self.name} managed transport is registered but not yet enabled. "
                "No remote command was executed."
            ),
            safe_noop=True,
        )


class MiningCoreExecutor(_PlaceholderExecutor):
    name = "miningcore"
    actions = {"restart-miningcore-service"}


class LinuxExecutor(_PlaceholderExecutor):
    name = "linux"
    actions = {"linux.collect-diagnostics", "linux.restart-service"}


class AsicExecutor(_PlaceholderExecutor):
    name = "asic"
    actions = {"asic.collect-diagnostics", "asic.restart"}
