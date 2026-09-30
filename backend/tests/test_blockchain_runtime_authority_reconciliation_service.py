from __future__ import annotations

import unittest
from unittest.mock import MagicMock
from datetime import datetime, timedelta, timezone

from backend.services.blockchain_runtime_authority_reconciliation_service import (
    BlockchainRuntimeAuthorityReconciliationService,
    _projection_input,
)


class _Projection:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def project(
        self,
        *,
        provider_id,
        target_asset_id,
        storage_target_id,
    ):
        self.calls.append({
            "provider_id": provider_id,
            "target_asset_id": target_asset_id,
            "storage_target_id": storage_target_id,
        })

        if self.error:
            raise self.error

        return {
            "status": "ok",
        }


def _operation(
    *,
    operation_id="change-1",
    target_id="asset-1",
    result_data=None,
    completed_at=None,
):
    if result_data is None:
        result_data = {
            "providerId": "bitcoin-mainnet",
            "targetAssetId": "asset-1",
            "storageTargetId": "storage-1",
            "correlationId": "corr-1",
            "approvedBy": "operator-1",
        }

    if completed_at is None:
        completed_at = datetime(
            2026,
            9,
            29,
            12,
            0,
            tzinfo=timezone.utc,
        )

    return {
        "operation_id": operation_id,
        "action_name": "blockchain.install",
        "target_id": target_id,
        "asset_id": target_id,
        "correlation_id": "corr-queue",
        "confirmed_by": "queue-operator",
        "result_data": result_data,
        "completed_at": completed_at,
    }


class _StateStore:
    def __init__(self, state=None):
        self.state = dict(
            state
            or {
                "phase": "dated",
                "after_completed_at": None,
                "after_operation_id": None,
            }
        )
        self.writes = []
        self.resets = 0

    def read(self):
        return dict(self.state)

    def write(
        self,
        *,
        phase,
        after_completed_at=None,
        after_operation_id=None,
    ):
        self.state = {
            "phase": phase,
            "after_completed_at":
                after_completed_at,
            "after_operation_id":
                after_operation_id,
        }
        self.writes.append(
            dict(self.state)
        )

    def reset(self):
        self.resets += 1
        self.state = {
            "phase": "dated",
            "after_completed_at": None,
            "after_operation_id": None,
        }


class _KeysetReader:
    def __init__(
        self,
        *,
        dated=None,
        null=None,
    ):
        self.dated = list(dated or [])
        self.null = list(null or [])
        self.calls = []

    def __call__(
        self,
        *,
        limit,
        after_completed_at=None,
        after_operation_id=None,
        include_null_completed_at=False,
    ):
        self.calls.append({
            "limit": limit,
            "after_completed_at":
                after_completed_at,
            "after_operation_id":
                after_operation_id,
            "include_null_completed_at":
                include_null_completed_at,
        })

        if include_null_completed_at:
            rows = self.null

            if after_operation_id is not None:
                rows = [
                    row
                    for row in rows
                    if row["operation_id"]
                    < after_operation_id
                ]

            return rows[:limit]

        rows = self.dated

        if after_completed_at is not None:
            cursor = (
                after_completed_at,
                after_operation_id,
            )

            rows = [
                row
                for row in rows
                if (
                    row["completed_at"],
                    row["operation_id"],
                ) < cursor
            ]

        return rows[:limit]


class BlockchainRuntimeAuthorityReconciliationTests(
    unittest.TestCase
):
    def _service(
        self,
        *,
        projection=None,
        reader=None,
        state=None,
    ):
        projection = projection or _Projection()
        reader = reader or _KeysetReader()
        state = state or _StateStore()

        service = (
            BlockchainRuntimeAuthorityReconciliationService(
                projection_service=projection,
                reader=reader,
                state_reader=state.read,
                state_writer=state.write,
                state_resetter=state.reset,
            )
        )

        return service, projection, reader, state

    def test_replays_complete_durable_result(self):
        operation = _operation()
        reader = _KeysetReader(
            dated=[operation],
        )

        service, projection, _, state = (
            self._service(reader=reader)
        )

        result = service.reconcile(limit=1)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["evaluated"], 1)
        self.assertEqual(result["projected"], 1)
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(result["failed"], 0)

        self.assertEqual(
            projection.calls,
            [{
                "provider_id": "bitcoin-mainnet",
                "target_asset_id": "asset-1",
                "storage_target_id": "storage-1",
            }],
        )

        self.assertEqual(
            state.state["after_operation_id"],
            "change-1",
        )

    def test_missing_result_field_fails_closed_and_advances(self):
        operation = _operation(
            operation_id="change-2",
            result_data={
                "providerId": "bitcoin-mainnet",
                "targetAssetId": "asset-1",
            },
        )

        service, projection, _, state = self._service(
            reader=_KeysetReader(
                dated=[operation],
            )
        )

        result = service.reconcile(limit=1)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["projected"], 0)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(projection.calls, [])
        self.assertEqual(
            state.state["after_operation_id"],
            "change-2",
        )

    def test_target_mismatch_fails_closed(self):
        operation = _operation(
            operation_id="change-3",
            target_id="asset-other",
        )

        service, projection, _, state = self._service(
            reader=_KeysetReader(
                dated=[operation],
            )
        )

        result = service.reconcile(limit=1)

        self.assertEqual(result["projected"], 0)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(projection.calls, [])
        self.assertEqual(
            state.state["after_operation_id"],
            "change-3",
        )

    def test_projection_failure_is_warning_only_and_advances(self):
        operation = _operation(
            operation_id="change-4",
        )
        projection = _Projection(
            RuntimeError("projection unavailable")
        )

        service, projection, _, state = self._service(
            projection=projection,
            reader=_KeysetReader(
                dated=[operation],
            ),
        )

        result = service.reconcile(limit=1)

        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["evaluated"], 1)
        self.assertEqual(result["projected"], 0)
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(len(projection.calls), 1)
        self.assertEqual(
            state.state["after_operation_id"],
            "change-4",
        )

    def test_projection_value_error_is_failure(self):
        operation = _operation(
            operation_id="change-5",
        )
        projection = _Projection(
            ValueError(
                "projection rejected authority"
            )
        )

        service, projection, _, state = self._service(
            projection=projection,
            reader=_KeysetReader(
                dated=[operation],
            ),
        )

        result = service.reconcile(limit=1)

        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["projected"], 0)
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(len(projection.calls), 1)
        self.assertEqual(
            state.state["after_operation_id"],
            "change-5",
        )

    def test_empty_success_set_transitions_dated_to_null_then_wraps(self):
        service, projection, reader, state = (
            self._service()
        )

        result = service.reconcile(limit=10)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["evaluated"], 0)
        self.assertEqual(result["projected"], 0)
        self.assertEqual(projection.calls, [])
        self.assertEqual(len(reader.calls), 2)

        self.assertFalse(
            reader.calls[0][
                "include_null_completed_at"
            ]
        )
        self.assertTrue(
            reader.calls[1][
                "include_null_completed_at"
            ]
        )

        self.assertEqual(state.resets, 1)
        self.assertEqual(
            state.state["phase"],
            "dated",
        )

    def test_projection_input_matches_exact_projection_api(self):
        result = _projection_input(
            _operation()
        )

        self.assertEqual(
            result,
            {
                "provider_id": "bitcoin-mainnet",
                "target_asset_id": "asset-1",
                "storage_target_id": "storage-1",
            },
        )

    def test_work_is_bounded_and_next_run_continues(self):
        base = datetime(
            2026,
            9,
            29,
            12,
            0,
            tzinfo=timezone.utc,
        )

        rows = [
            _operation(
                operation_id=f"change-{index:03d}",
                completed_at=(
                    base
                    - timedelta(seconds=index)
                ),
            )
            for index in range(1, 7)
        ]

        reader = _KeysetReader(
            dated=rows,
        )
        state = _StateStore()

        first_service, first_projection, _, _ = (
            self._service(
                reader=reader,
                state=state,
            )
        )

        first = first_service.reconcile(
            limit=3
        )

        self.assertEqual(
            first["evaluated"],
            3,
        )
        self.assertEqual(
            len(first_projection.calls),
            3,
        )
        self.assertEqual(
            state.state["after_operation_id"],
            "change-003",
        )

        second_service, second_projection, _, _ = (
            self._service(
                reader=reader,
                state=state,
            )
        )

        second = second_service.reconcile(
            limit=3
        )

        self.assertEqual(
            second["evaluated"],
            3,
        )
        self.assertEqual(
            len(second_projection.calls),
            3,
        )
        self.assertEqual(
            state.state["after_operation_id"],
            "change-006",
        )

        projected_ids = [
            call["target_asset_id"]
            for call in (
                first_projection.calls
                + second_projection.calls
            )
        ]

        self.assertEqual(
            len(projected_ids),
            6,
        )

    def test_dated_exhaustion_continues_into_null_phase_with_remaining_budget(self):
        dated = _operation(
            operation_id="dated-1",
        )

        legacy = _operation(
            operation_id="legacy-1",
        )
        legacy["completed_at"] = None

        reader = _KeysetReader(
            dated=[dated],
            null=[legacy],
        )

        service, projection, reader, state = (
            self._service(
                reader=reader,
            )
        )

        result = service.reconcile(
            limit=2
        )

        self.assertEqual(
            result["evaluated"],
            2,
        )
        self.assertEqual(
            result["projected"],
            2,
        )
        self.assertEqual(
            len(projection.calls),
            2,
        )
        self.assertEqual(
            state.state["phase"],
            "null",
        )
        self.assertEqual(
            state.state["after_operation_id"],
            "legacy-1",
        )

        self.assertTrue(
            any(
                call[
                    "include_null_completed_at"
                ]
                for call in reader.calls
            )
        )

    def test_null_exhaustion_wraps_for_future_new_successes(self):
        legacy = _operation(
            operation_id="legacy-1",
        )
        legacy["completed_at"] = None

        state = _StateStore({
            "phase": "null",
            "after_completed_at": None,
            "after_operation_id": None,
        })

        reader = _KeysetReader(
            null=[legacy],
        )

        service, _, _, state = (
            self._service(
                reader=reader,
                state=state,
            )
        )

        first = service.reconcile(limit=1)

        self.assertEqual(first["evaluated"], 1)
        self.assertEqual(
            state.state["phase"],
            "null",
        )

        service, _, _, state = (
            self._service(
                reader=reader,
                state=state,
            )
        )

        second = service.reconcile(limit=1)

        self.assertEqual(second["evaluated"], 0)
        self.assertEqual(state.resets, 1)
        self.assertEqual(
            state.state["phase"],
            "dated",
        )

    def test_limit_is_capped_at_500(self):
        base = datetime(
            2026,
            9,
            29,
            12,
            0,
            tzinfo=timezone.utc,
        )

        rows = [
            _operation(
                operation_id=f"change-{index:04d}",
                completed_at=(
                    base
                    - timedelta(seconds=index)
                ),
            )
            for index in range(1, 502)
        ]

        service, projection, _, state = (
            self._service(
                reader=_KeysetReader(
                    dated=rows,
                )
            )
        )

        result = service.reconcile(
            limit=5000
        )

        self.assertEqual(
            result["evaluated"],
            500,
        )
        self.assertEqual(
            len(projection.calls),
            500,
        )
        self.assertEqual(
            state.state["after_operation_id"],
            "change-0500",
        )

    def test_invalid_limit_fails_closed(self):
        service, _, _, _ = (
            self._service()
        )

        with self.assertRaises(ValueError):
            service.reconcile(limit=0)

    def test_incomplete_persisted_dated_cursor_fails_closed(self):
        state = _StateStore({
            "phase": "dated",
            "after_completed_at": None,
            "after_operation_id": "change-100",
        })

        service, projection, reader, _ = (
            self._service(
                state=state,
            )
        )

        with self.assertRaises(ValueError):
            service.reconcile(limit=10)

        self.assertEqual(
            projection.calls,
            [],
        )
        self.assertEqual(
            reader.calls,
            [],
        )


if __name__ == "__main__":
    unittest.main()

class BlockchainRuntimeAuthorityReconciliationSerializationTests(unittest.TestCase):
    def test_busy_cross_process_lock_skips_without_reading_checkpoint(self):
        state_reader = MagicMock()

        service = BlockchainRuntimeAuthorityReconciliationService(
            state_reader=state_reader,
            lock_acquirer=lambda: None,
            lock_releaser=MagicMock(),
        )

        result = service.reconcile(limit=100)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["source"],
                         "blockchain-runtime-authority-reconciliation")
        self.assertTrue(result["serializationSkipped"])
        self.assertEqual(result["evaluated"], 0)
        self.assertEqual(result["projected"], 0)
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(result["failed"], 0)
        state_reader.assert_not_called()

    def test_lock_is_held_across_complete_reconciliation_cycle(self):
        events = []
        lock_handle = object()

        def acquire():
            events.append("acquire")
            return lock_handle

        def read_state():
            events.append("read-state")
            return {
                "phase": "dated",
                "after_completed_at": None,
                "after_operation_id": None,
            }

        def reader(**kwargs):
            events.append("read-page")
            return []

        def write_state(**kwargs):
            events.append("write-state")

        def reset_state():
            events.append("reset-state")

        def release(handle):
            self.assertIs(handle, lock_handle)
            events.append("release")

        service = BlockchainRuntimeAuthorityReconciliationService(
            reader=reader,
            state_reader=read_state,
            state_writer=write_state,
            state_resetter=reset_state,
            lock_acquirer=acquire,
            lock_releaser=release,
        )

        result = service.reconcile(limit=100)

        self.assertFalse(result["serializationSkipped"])
        self.assertEqual(events[0], "acquire")
        self.assertEqual(events[-1], "release")
        self.assertIn("read-state", events)
        self.assertIn("write-state", events)
        self.assertIn("reset-state", events)

    def test_lock_is_released_when_reconciliation_raises(self):
        lock_handle = object()
        release = MagicMock()

        def explode():
            raise RuntimeError("checkpoint read failed")

        service = BlockchainRuntimeAuthorityReconciliationService(
            state_reader=explode,
            lock_acquirer=lambda: lock_handle,
            lock_releaser=release,
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "checkpoint read failed",
        ):
            service.reconcile(limit=100)

        release.assert_called_once_with(lock_handle)

    def test_invalid_limit_fails_before_lock_acquisition(self):
        for invalid_limit in (0, "not-an-int"):
            with self.subTest(limit=invalid_limit):
                lock_acquirer = MagicMock()

                service = BlockchainRuntimeAuthorityReconciliationService(
                    lock_acquirer=lock_acquirer,
                )

                with self.assertRaises((TypeError, ValueError)):
                    service.reconcile(limit=invalid_limit)

                lock_acquirer.assert_not_called()
