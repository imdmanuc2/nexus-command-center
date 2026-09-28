from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

from backend.core.operation_execution_control import (
    OperationCancellationRequested,
    OperationLeaseLost,
)

from backend.db.repositories import (
    change_execution_repository as repo,
)


class _Cursor:
    def __init__(self, selected):
        self.selected = selected
        self.updated = None
        self.calls = []
        self._fetch_count = 0

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchone(self):
        self._fetch_count += 1

        if self._fetch_count == 1:
            return self.selected

        return self.updated

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _Connection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _Transaction:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, *args):
        return False


class ChangeExecutionCheckpointTests(
    unittest.TestCase
):
    def _run(
        self,
        selected,
        *,
        updated=None,
        current_step=3,
        total_steps=7,
        lease_seconds=120,
    ):
        cursor = _Cursor(selected)
        cursor.updated = updated

        connection = _Connection(cursor)

        with patch.object(
            repo,
            "transaction",
            return_value=_Transaction(connection),
        ):
            result = repo.checkpoint_operation(
                "op-1",
                "worker-1",
                current_step,
                total_steps,
                lease_seconds,
            )

        return result, cursor

    def test_signature_is_generic(self):
        signature = inspect.signature(
            repo.checkpoint_operation
        )

        self.assertEqual(
            list(signature.parameters),
            [
                "operation_id",
                "worker_id",
                "current_step",
                "total_steps",
                "lease_seconds",
            ],
        )

    def test_checkpoint_renews_owned_running_operation(self):
        result, cursor = self._run(
            {
                "operation_id": "op-1",
                "status": "running",
                "lease_owner": "worker-1",
                "cancellation_requested": False,
            },
            updated={
                "operation_id": "op-1",
                "status": "running",
                "lease_owner": "worker-1",
                "current_step": 3,
                "total_steps": 7,
                "progress_percent": 28,
            },
        )

        self.assertEqual(
            result["operation_id"],
            "op-1",
        )

        self.assertEqual(len(cursor.calls), 2)

        update_sql, update_params = (
            cursor.calls[1]
        )

        self.assertIn(
            "lease_expires_at",
            update_sql,
        )
        self.assertIn(
            "heartbeat_at=NOW()",
            update_sql,
        )
        self.assertIn(
            "cancellation_requested=FALSE",
            update_sql,
        )

        self.assertEqual(
            update_params,
            (
                120,
                3,
                7,
                28,
                "op-1",
                "worker-1",
            ),
        )

    def test_cancellation_fails_before_update(self):
        cursor = _Cursor(
            {
                "operation_id": "op-1",
                "status": "running",
                "lease_owner": "worker-1",
                "cancellation_requested": True,
            }
        )

        connection = _Connection(cursor)

        with patch.object(
            repo,
            "transaction",
            return_value=_Transaction(connection),
        ):
            with self.assertRaisesRegex(
                OperationCancellationRequested,
                "cancellation requested",
            ):
                repo.checkpoint_operation(
                    "op-1",
                    "worker-1",
                    2,
                    7,
                )

        self.assertEqual(len(cursor.calls), 1)

    def test_wrong_lease_owner_fails_closed(self):
        cursor = _Cursor(
            {
                "operation_id": "op-1",
                "status": "running",
                "lease_owner": "worker-other",
                "cancellation_requested": False,
            }
        )

        connection = _Connection(cursor)

        with patch.object(
            repo,
            "transaction",
            return_value=_Transaction(connection),
        ):
            with self.assertRaisesRegex(
                OperationLeaseLost,
                "lease ownership was lost",
            ):
                repo.checkpoint_operation(
                    "op-1",
                    "worker-1",
                    2,
                    7,
                )

        self.assertEqual(len(cursor.calls), 1)

    def test_non_running_operation_fails_closed(self):
        cursor = _Cursor(
            {
                "operation_id": "op-1",
                "status": "queued",
                "lease_owner": "worker-1",
                "cancellation_requested": False,
            }
        )

        connection = _Connection(cursor)

        with patch.object(
            repo,
            "transaction",
            return_value=_Transaction(connection),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "no longer running",
            ):
                repo.checkpoint_operation(
                    "op-1",
                    "worker-1",
                    2,
                    7,
                )

        self.assertEqual(len(cursor.calls), 1)

    def test_missing_operation_fails_closed(self):
        cursor = _Cursor(None)
        connection = _Connection(cursor)

        with patch.object(
            repo,
            "transaction",
            return_value=_Transaction(connection),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "no longer exists",
            ):
                repo.checkpoint_operation(
                    "op-1",
                    "worker-1",
                    2,
                    7,
                )

    def test_lost_atomic_update_fails_closed(self):
        with self.assertRaisesRegex(
            OperationLeaseLost,
            "checkpoint lost ownership",
        ):
            self._run(
                {
                    "operation_id": "op-1",
                    "status": "running",
                    "lease_owner": "worker-1",
                    "cancellation_requested": False,
                },
                updated=None,
            )

    def test_invalid_step_rejected_without_db(self):
        with patch.object(
            repo,
            "transaction",
        ) as transaction:
            with self.assertRaises(ValueError):
                repo.checkpoint_operation(
                    "op-1",
                    "worker-1",
                    0,
                    7,
                )

            transaction.assert_not_called()

    def test_invalid_total_rejected_without_db(self):
        with patch.object(
            repo,
            "transaction",
        ) as transaction:
            with self.assertRaises(ValueError):
                repo.checkpoint_operation(
                    "op-1",
                    "worker-1",
                    1,
                    0,
                )

            transaction.assert_not_called()

    def test_invalid_lease_rejected_without_db(self):
        with patch.object(
            repo,
            "transaction",
        ) as transaction:
            with self.assertRaises(ValueError):
                repo.checkpoint_operation(
                    "op-1",
                    "worker-1",
                    1,
                    7,
                    0,
                )

            transaction.assert_not_called()


if __name__ == "__main__":
    unittest.main()
