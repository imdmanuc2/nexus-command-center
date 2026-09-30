from __future__ import annotations

import os
import socket
from typing import Any

from backend.capabilities.registry import get_capability_registry
from backend.core.operation_execution_control import (
    OperationCancellationRequested,
    OperationLeaseLost,
)
from backend.db.repositories import change_execution_repository as repo
from backend.services.blockchain_change_execution_adapter import (
    BlockchainChangeExecutionAdapter,
)
from backend.services.blockchain_change_execution_dispatch_service import (
    BlockchainChangeExecutionDispatchService,
)
from backend.transports.registry import get_transport_registry
from backend.transports.target_resolver import resolve_target
from backend.services.blockchain_runtime_authority_projection_service import BlockchainRuntimeAuthorityProjectionService


def _blockchain_install_dispatch():
    return BlockchainChangeExecutionDispatchService(
        adapter_factory=BlockchainChangeExecutionAdapter,
    )


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
        if operation.get("action_name") == "blockchain.install":
            dispatch = _blockchain_install_dispatch()

            deployment_result = dispatch.execute(
                operation,
                change,
                worker_id,
            )

            result = dispatch.result_data(
                deployment_result
            )

            if not deployment_result.ok:
                raise RuntimeError(
                    deployment_result.error
                    or "Blockchain deployment failed"
                )

            repo.finish_success(
                attempt_id,
                operation,
                change,
                result,
                worker_id,
            )

            try:
                BlockchainRuntimeAuthorityProjectionService().project(
                    provider_id=deployment_result.provider_id,
                    target_asset_id=deployment_result.target_asset_id,
                    storage_target_id=deployment_result.storage_target_id,
                )
            except Exception:
                pass

            return {
                "status": "succeeded",
                "operationId": operation["operation_id"],
                "result": result,
            }

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

        repo.finish_success(
            attempt_id,
            operation,
            change,
            result,
            worker_id,
        )
        return {"status":"succeeded","operationId":operation["operation_id"],"result":result}
    except OperationCancellationRequested as exc:
        try:
            repo.finish_cancelled(
                attempt_id,
                operation,
                change,
                worker_id,
                str(exc),
            )
        except OperationLeaseLost:
            return {
                "status": "lease-lost",
                "operationId": operation["operation_id"],
                "result": result,
            }

        return {
            "status": "cancelled",
            "operationId": operation["operation_id"],
            "message": str(exc),
            "result": result,
        }

    except OperationLeaseLost:
        return {
            "status": "lease-lost",
            "operationId": operation["operation_id"],
            "result": result,
        }

    except Exception as exc:
        try:
            repo.finish_failure(
                attempt_id,
                operation,
                change,
                str(exc),
                result,
                worker_id,
            )
        except OperationLeaseLost:
            return {
                "status": "lease-lost",
                "operationId": operation["operation_id"],
                "result": result,
            }

        return {
            "status": "failed",
            "operationId": operation["operation_id"],
            "error": str(exc),
            "result": result,
        }


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
