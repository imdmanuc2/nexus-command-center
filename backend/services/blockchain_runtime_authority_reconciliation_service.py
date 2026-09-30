from __future__ import annotations

from typing import Any

from backend.db.repositories.blockchain_runtime_authority_reconciliation_repository import (
    get_state,
    release_reconciliation_lock,
    reset_state,
    try_acquire_reconciliation_lock,
    update_state,
)
from backend.db.repositories.change_execution_repository import (
    list_successful_blockchain_install_results,
)
from backend.services.blockchain_runtime_authority_projection_service import (
    BlockchainRuntimeAuthorityProjectionService,
)


_REQUIRED_RESULT_FIELDS = (
    "providerId",
    "targetAssetId",
    "storageTargetId",
)

_PHASE_DATED = "dated"
_PHASE_NULL = "null"


def _required_text(
    payload: dict[str, Any],
    name: str,
) -> str:
    value = str(payload.get(name) or "").strip()

    if not value:
        raise ValueError(
            f"Successful blockchain.install result "
            f"is missing {name}"
        )

    return value


def _projection_input(
    operation: dict[str, Any],
) -> dict[str, str]:
    result = operation.get("result_data")

    if not isinstance(result, dict):
        raise ValueError(
            "Successful blockchain.install result_data "
            "must be an object"
        )

    values = {
        name: _required_text(result, name)
        for name in _REQUIRED_RESULT_FIELDS
    }

    target_id = str(
        operation.get("target_id")
        or operation.get("asset_id")
        or ""
    ).strip()

    if (
        target_id
        and target_id != values["targetAssetId"]
    ):
        raise ValueError(
            "Successful blockchain.install target identity "
            "does not match persisted deployment result"
        )

    return {
        "provider_id": values["providerId"],
        "target_asset_id": values["targetAssetId"],
        "storage_target_id": values["storageTargetId"],
    }


class BlockchainRuntimeAuthorityReconciliationService:
    """Replay durable deployment success into canonical CMDB authority.

    This service never executes blockchain lifecycle work. It only
    replays already-successful operation evidence through the existing
    idempotent authority projection boundary.

    Replay progress is persisted independently of projection outcome so
    malformed or permanently unprojectable historical rows cannot pin
    bounded reconciliation work forever.
    """

    def __init__(
        self,
        *,
        projection_service=None,
        reader=None,
        state_reader=None,
        state_writer=None,
        state_resetter=None,
        lock_acquirer=None,
        lock_releaser=None,
    ) -> None:
        self._projection_service = (
            projection_service
            or BlockchainRuntimeAuthorityProjectionService()
        )
        self._reader = (
            reader
            or list_successful_blockchain_install_results
        )
        self._state_reader = (
            state_reader
            or get_state
        )
        self._state_writer = (
            state_writer
            or update_state
        )
        self._state_resetter = (
            state_resetter
            or reset_state
        )
        self._lock_acquirer = (
            lock_acquirer
            or try_acquire_reconciliation_lock
        )
        self._lock_releaser = (
            lock_releaser
            or release_reconciliation_lock
        )

    def _read_page(
        self,
        *,
        state: dict[str, Any],
        limit: int,
    ) -> list[dict[str, Any]]:
        phase = str(
            state.get("phase") or _PHASE_DATED
        ).strip()

        if phase == _PHASE_DATED:
            completed_at = state.get(
                "after_completed_at"
            )
            operation_id = (
                str(
                    state.get(
                        "after_operation_id"
                    )
                    or ""
                ).strip()
                or None
            )

            kwargs: dict[str, Any] = {
                "limit": limit,
            }

            if (
                completed_at is not None
                or operation_id is not None
            ):
                if (
                    completed_at is None
                    or operation_id is None
                ):
                    raise ValueError(
                        "Persisted dated authority cursor "
                        "is incomplete"
                    )

                kwargs.update({
                    "after_completed_at":
                        completed_at,
                    "after_operation_id":
                        operation_id,
                })

            return self._reader(**kwargs)

        if phase == _PHASE_NULL:
            operation_id = (
                str(
                    state.get(
                        "after_operation_id"
                    )
                    or ""
                ).strip()
                or None
            )

            kwargs = {
                "limit": limit,
                "include_null_completed_at": True,
            }

            if operation_id is not None:
                kwargs["after_operation_id"] = (
                    operation_id
                )

            return self._reader(**kwargs)

        raise ValueError(
            "Persisted authority reconciliation phase "
            "must be dated or null"
        )

    def _advance_state(
        self,
        *,
        phase: str,
        operation: dict[str, Any],
    ) -> None:
        operation_id = str(
            operation.get("operation_id") or ""
        ).strip()

        if not operation_id:
            raise ValueError(
                "Successful blockchain.install replay row "
                "is missing operation_id"
            )

        if phase == _PHASE_DATED:
            completed_at = operation.get(
                "completed_at"
            )

            if completed_at is None:
                raise ValueError(
                    "Dated blockchain.install replay row "
                    "is missing completed_at"
                )

            self._state_writer(
                phase=_PHASE_DATED,
                after_completed_at=completed_at,
                after_operation_id=operation_id,
            )
            return

        if phase == _PHASE_NULL:
            self._state_writer(
                phase=_PHASE_NULL,
                after_completed_at=None,
                after_operation_id=operation_id,
            )
            return

        raise ValueError(
            "Authority reconciliation phase "
            "must be dated or null"
        )

    def _process_operation(
        self,
        operation: dict[str, Any],
        failures: list[dict[str, str]],
    ) -> tuple[int, int, int]:
        operation_id = str(
            operation.get("operation_id") or ""
        ).strip()

        try:
            projection_input = _projection_input(
                operation
            )
        except ValueError as exc:
            failures.append({
                "operationId": operation_id,
                "error": str(exc),
            })
            return 0, 1, 0

        try:
            self._projection_service.project(
                **projection_input
            )
        except Exception as exc:
            failures.append({
                "operationId": operation_id,
                "error": str(exc),
            })
            return 0, 0, 1

        return 1, 0, 0

    def reconcile(
        self,
        *,
        limit: int = 100,
    ) -> dict[str, Any]:
        limit = int(limit)

        if limit < 1:
            raise ValueError(
                "limit must be positive"
            )

        limit = min(limit, 500)

        lock_handle = self._lock_acquirer()

        if lock_handle is None:
            return {
                "status": "ok",
                "source": "blockchain-runtime-authority-reconciliation",
                "serializationSkipped": True,
                "evaluated": 0,
                "projected": 0,
                "skipped": 0,
                "failed": 0,
                "failures": [],
            }

        try:

            state = dict(self._state_reader() or {})
            phase = str(
                state.get("phase") or _PHASE_DATED
            ).strip()

            projected = 0
            skipped = 0
            failed = 0
            evaluated = 0
            failures: list[dict[str, str]] = []

            while evaluated < limit:
                remaining = limit - evaluated

                operations = self._read_page(
                    state=state,
                    limit=remaining,
                )

                if not operations:
                    if phase == _PHASE_DATED:
                        phase = _PHASE_NULL
                        state = {
                            "phase": _PHASE_NULL,
                            "after_completed_at": None,
                            "after_operation_id": None,
                        }

                        self._state_writer(
                            phase=_PHASE_NULL,
                            after_completed_at=None,
                            after_operation_id=None,
                        )
                        continue

                    self._state_resetter()
                    phase = _PHASE_DATED
                    state = {
                        "phase": _PHASE_DATED,
                        "after_completed_at": None,
                        "after_operation_id": None,
                    }
                    break

                for operation in operations:
                    current_phase = phase

                    operation_projected, operation_skipped, operation_failed = (
                        self._process_operation(
                            operation,
                            failures,
                        )
                    )

                    projected += operation_projected
                    skipped += operation_skipped
                    failed += operation_failed
                    evaluated += 1

                    self._advance_state(
                        phase=current_phase,
                        operation=operation,
                    )

                    if current_phase == _PHASE_DATED:
                        state = {
                            "phase": _PHASE_DATED,
                            "after_completed_at":
                                operation.get(
                                    "completed_at"
                                ),
                            "after_operation_id":
                                operation.get(
                                    "operation_id"
                                ),
                        }
                    else:
                        state = {
                            "phase": _PHASE_NULL,
                            "after_completed_at": None,
                            "after_operation_id":
                                operation.get(
                                    "operation_id"
                                ),
                        }

                    if evaluated >= limit:
                        break

            return {
                "status": (
                    "ok"
                    if failed == 0
                    else "warning"
                ),
                "source":
                    "blockchain-runtime-authority-reconciliation",
                "serializationSkipped": False,
                "evaluated": evaluated,
                "projected": projected,
                "skipped": skipped,
                "failed": failed,
                "failures": failures,
                "phase": state["phase"],
                "afterCompletedAt":
                    state.get("after_completed_at"),
                "afterOperationId":
                    state.get("after_operation_id"),
            }
        finally:
            self._lock_releaser(lock_handle)
