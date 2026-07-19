from __future__ import annotations

import time
from typing import Any

from backend.capabilities.registry import get_capability_registry
from backend.executors.base_executor import BaseExecutor
from backend.executors.results import ExecutionResult
from backend.transports.registry import get_transport_registry
from backend.transports.target_resolver import resolve_target


class ManagedHostExecutor(BaseExecutor):
    name = "managed-host"
    ACTIONS = {
        "host.identity", "host.disk-usage", "host.memory",
        "service.status", "service.restart", "service.journal",
    }

    def supports(self, action_id: str, run: dict[str, Any]) -> bool:
        return action_id in self.ACTIONS

    def validate(self, run: dict[str, Any]) -> None:
        super().validate(run)
        payload = run.get("inputPayload") or {}
        forbidden = {"command", "shell", "argv"} & set(payload)
        if forbidden:
            raise ValueError("Arbitrary command execution is prohibited")
        capability = get_capability_registry().resolve(run["actionId"])
        params = payload.get("parameters") or {}
        if not isinstance(params, dict):
            raise ValueError("parameters must be an object")
        get_capability_registry().validate_parameters(capability, params)
        if capability.requires_approval and not run.get("approvedBy"):
            raise ValueError("Capability requires an approved automation run")
        if not str(payload.get("correlationId") or run.get("runId") or "").strip():
            raise ValueError("Execution requires correlationId")

    def execute(self, run: dict[str, Any]) -> ExecutionResult:
        self.validate(run)
        started = time.perf_counter()
        payload = run.get("inputPayload") or {}
        params = payload.get("parameters") or {}
        capability = get_capability_registry().resolve(run["actionId"])
        target = resolve_target(run)
        transport = get_transport_registry().resolve(target.transport)
        secrets = payload.get("redactValues") or []

        primary = transport.execute(
            target=target, argv=capability.build_argv(params),
            timeout_seconds=capability.timeout_seconds, secrets=secrets,
        )
        details: dict[str, Any] = {
            "capabilityId": capability.capability_id,
            "correlationId": payload.get("correlationId") or run.get("runId"),
            "approvalCorrelation": run.get("approvedBy") or None,
            "execution": primary.to_dict(),
            "verification": None,
        }
        ok = primary.ok
        partial = False
        if primary.ok and capability.verify_argv:
            verification = transport.execute(
                target=target, argv=capability.verify_argv(params),
                timeout_seconds=min(capability.timeout_seconds, 30), secrets=secrets,
            )
            details["verification"] = verification.to_dict()
            ok = verification.ok and "ActiveState=active" in verification.stdout
            partial = primary.ok and not ok

        status = "completed" if ok else "failed"
        summary = (
            f"Capability {capability.capability_id} completed and verified."
            if ok else
            f"Capability {capability.capability_id} partially succeeded but verification failed."
            if partial else
            f"Capability {capability.capability_id} failed."
        )
        return ExecutionResult(
            status=status, executor=self.name, action=run["actionId"],
            entity_type=run["entityType"], entity_id=run["entityId"],
            summary=summary, details=details,
            duration_ms=round((time.perf_counter()-started)*1000),
        )
