from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from backend.db.repositories import (
    blockchain_runtime_authority_reconciliation_repository as repository,
)


class _Cursor:
    def __init__(self, row=None):
        self.row = row
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchone(self):
        return self.row

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _Connection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class BlockchainRuntimeAuthorityReconciliationRepositoryTests(
    unittest.TestCase
):
    def test_missing_state_returns_dated_start(self):
        cursor = _Cursor(row=None)

        with patch.object(
            repository,
            "get_connection",
            return_value=_Connection(cursor),
        ):
            state = repository.get_state()

        self.assertEqual(
            state,
            {
                "engine_name":
                    "blockchain-runtime-authority-reconciliation",
                "phase": "dated",
                "after_completed_at": None,
                "after_operation_id": None,
            },
        )

    def test_persist_dated_cursor_uses_upsert(self):
        cursor = _Cursor()
        completed_at = datetime(
            2026,
            9,
            29,
            12,
            30,
            tzinfo=timezone.utc,
        )

        with patch.object(
            repository,
            "transaction",
            return_value=_Connection(cursor),
        ):
            repository.update_state(
                phase="dated",
                after_completed_at=completed_at,
                after_operation_id="change-100",
            )

        self.assertEqual(len(cursor.calls), 1)

        sql, params = cursor.calls[0]

        self.assertIn("ON CONFLICT (engine_name)", sql)
        self.assertIn("DO UPDATE SET", sql)
        self.assertEqual(
            params,
            (
                "blockchain-runtime-authority-reconciliation",
                "dated",
                completed_at,
                "change-100",
            ),
        )

    def test_persist_null_cursor_uses_operation_id_only(self):
        cursor = _Cursor()

        with patch.object(
            repository,
            "transaction",
            return_value=_Connection(cursor),
        ):
            repository.update_state(
                phase="null",
                after_operation_id="change-050",
            )

        _, params = cursor.calls[0]

        self.assertEqual(
            params,
            (
                "blockchain-runtime-authority-reconciliation",
                "null",
                None,
                "change-050",
            ),
        )

    def test_reset_returns_to_dated_start(self):
        with patch.object(
            repository,
            "update_state",
        ) as update_state:
            repository.reset_state()

        update_state.assert_called_once_with(
            phase="dated",
            after_completed_at=None,
            after_operation_id=None,
        )

    def test_invalid_phase_fails_before_database(self):
        with patch.object(
            repository,
            "transaction",
        ) as transaction:
            with self.assertRaises(ValueError):
                repository.update_state(
                    phase="other",
                )

        transaction.assert_not_called()

    def test_partial_dated_cursor_fails_before_database(self):
        with patch.object(
            repository,
            "transaction",
        ) as transaction:
            with self.assertRaises(ValueError):
                repository.update_state(
                    phase="dated",
                    after_operation_id="change-100",
                )

        transaction.assert_not_called()

    def test_null_phase_rejects_completed_at(self):
        completed_at = datetime(
            2026,
            9,
            29,
            tzinfo=timezone.utc,
        )

        with patch.object(
            repository,
            "transaction",
        ) as transaction:
            with self.assertRaises(ValueError):
                repository.update_state(
                    phase="null",
                    after_completed_at=completed_at,
                )

        transaction.assert_not_called()


if __name__ == "__main__":
    unittest.main()

class BlockchainRuntimeAuthorityReconciliationLockContractTests(unittest.TestCase):
    def test_try_acquire_reconciliation_lock_uses_session_advisory_lock(self):
        connection = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = {"acquired": True}
        connection.cursor.return_value.__enter__.return_value = cursor

        with patch(
            "backend.db.repositories."
            "blockchain_runtime_authority_reconciliation_repository."
            "get_connection",
            return_value=connection,
        ):
            from backend.db.repositories import (
                blockchain_runtime_authority_reconciliation_repository
                as repository,
            )

            acquired = repository.try_acquire_reconciliation_lock()

        self.assertIs(acquired, connection)

        sql = cursor.execute.call_args.args[0]
        self.assertIn("pg_try_advisory_lock", sql)
        self.assertNotIn("pg_try_advisory_xact_lock", sql)

    def test_try_acquire_reconciliation_lock_closes_connection_when_busy(self):
        connection = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = {"acquired": False}
        connection.cursor.return_value.__enter__.return_value = cursor

        with patch(
            "backend.db.repositories."
            "blockchain_runtime_authority_reconciliation_repository."
            "get_connection",
            return_value=connection,
        ):
            from backend.db.repositories import (
                blockchain_runtime_authority_reconciliation_repository
                as repository,
            )

            acquired = repository.try_acquire_reconciliation_lock()

        self.assertIsNone(acquired)
        connection.close.assert_called_once_with()

    def test_release_reconciliation_lock_unlocks_before_close(self):
        connection = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = {"released": True}
        connection.cursor.return_value.__enter__.return_value = cursor

        from backend.db.repositories import (
            blockchain_runtime_authority_reconciliation_repository
            as repository,
        )

        repository.release_reconciliation_lock(connection)

        sql = cursor.execute.call_args.args[0]
        self.assertIn("pg_advisory_unlock", sql)
        connection.close.assert_called_once_with()
