from __future__ import annotations

import os
import socket
from typing import Any

from backend.capabilities.registry import get_capability_registry
from backend.db.repositories import change_execution_repository as repo
from backend.transports.registry import get_transport_registry
from backend.transports.target_resolver import resolve_target


def _target_input(operation):
    data = operation.get("input_data") or {}
    parameters = data.get("parameters") or {}
    return {
        "entityId": operation.get("asset_id") or operation.get("target_id"),
        "inputPayload": {
            "assetId": operation.get("asset_id") or operation.get("target_id"),
            "transport": parameters.pop("transport", "ssh"),
            **parameters,
        },
    }, parameters


def execute_operation(operation, worker_id: str):
    change = repo.find_change_for_operation(operation["operation_id"])
    attempt_id = repo.start_attempt(change, operation, worker_id)
    result = {}
    try:
        registry = get_capability_registry()
        capability = registry.resolve(operation["action_name"])
        run, parameters = _target_input(operation)
        registry.validate_parameters(capability, parameters)

        if capability.requires_approval and not operation.get("confirmed"):
            raise ValueError("Capability requires confirmed approval")

        target = resolve_target(run)
        transport = get_transport_registry().resolve(target.transport)
        timeout = min(int(operation.get("timeout_seconds") or capability.timeout_seconds),
                      int(capability.timeout_seconds))
        result_obj = transport.execute(
            target=target,
            argv=capability.build_argv(parameters),
            timeout_seconds=timeout,
        )
        result = result_obj.to_dict()
        if not result_obj.ok:
            raise RuntimeError(
                f"Execution failed with exit code {result_obj.exit_code}: "
                f"{result_obj.stderr or 'no error output'}"
            )

        if capability.verify_argv:
            verify_obj = transport.execute(
                target=target,
                argv=capability.verify_argv(parameters),
                timeout_seconds=timeout,
            )
            result["verification"] = verify_obj.to_dict()
            if not verify_obj.ok:
                raise RuntimeError("Post-action verification failed")

        repo.finish_success(attempt_id, operation, change, result)
        return {"status":"succeeded","operationId":operation["operation_id"],"result":result}
    except Exception as exc:
        repo.finish_failure(attempt_id, operation, change, str(exc), result)
        return {"status":"failed","operationId":operation["operation_id"],"error":str(exc),"result":result}


def run_once(worker_id: str):
    if not repo.queue_available():
        repo.heartbeat(worker_id, "idle")
        return {"status":"idle","queueAvailable":False,"recovered":[]}
    repo.heartbeat(worker_id, "claiming")
    recovered = repo.reconcile_stale()
    operation = repo.claim_next(worker_id)
    if not operation:
        repo.heartbeat(worker_id, "idle")
        return {"status":"idle","recovered":recovered}
    repo.heartbeat(worker_id, "running", operation["operation_id"])
    result = execute_operation(operation, worker_id)
    repo.heartbeat(worker_id, "idle")
    result["recovered"] = recovered
    return result


def status():
    return repo.status()


def history(limit=100):
    return repo.history(limit)
