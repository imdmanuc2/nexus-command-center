from __future__ import annotations

from typing import Any

from backend.executors.base_executor import BaseExecutor
from backend.executors.bitcoin_executor import BitcoinExecutor
from backend.executors.placeholder_executors import (
    AsicExecutor,
    LinuxExecutor,
    MiningCoreExecutor,
)


class ExecutorRegistry:
    def __init__(self) -> None:
        self._executors: list[BaseExecutor] = []

    def register(self, executor: BaseExecutor) -> None:
        self._executors.append(executor)

    def resolve(self, action_id: str, run: dict[str, Any]) -> BaseExecutor | None:
        for executor in self._executors:
            if executor.supports(action_id, run):
                return executor
        return None

    def describe(self) -> list[dict[str, Any]]:
        return [
            {
                "name": executor.name,
                "actions": sorted(getattr(executor, "ACTIONS", getattr(executor, "actions", set()))),
            }
            for executor in self._executors
        ]


_registry: ExecutorRegistry | None = None


def get_executor_registry() -> ExecutorRegistry:
    global _registry
    if _registry is None:
        _registry = ExecutorRegistry()
        _registry.register(BitcoinExecutor())
        _registry.register(MiningCoreExecutor())
        _registry.register(LinuxExecutor())
        _registry.register(AsicExecutor())
    return _registry
