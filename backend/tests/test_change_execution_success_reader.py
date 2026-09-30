from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from backend.db.repositories import change_execution_repository as repo


class _Cursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.execute_calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.execute_calls.append(
            (
                " ".join(str(sql).split()),
                tuple(params or ()),
            )
        )

    def fetchall(self):
        return list(self.rows)


class _Connection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self._cursor


class SuccessfulBlockchainInstallReaderTests(
    unittest.TestCase
):
    def _read(
        self,
        rows,
        **kwargs,
    ):
        cursor = _Cursor(rows)

        with (
            patch.object(
                repo,
                "queue_available",
                return_value=True,
            ),
            patch.object(
                repo,
                "get_connection",
                return_value=_Connection(cursor),
            ),
        ):
            result = (
                repo.list_successful_blockchain_install_results(
                    **kwargs
                )
            )

        self.assertEqual(
            len(cursor.execute_calls),
            1,
        )

        sql, params = cursor.execute_calls[0]

        return result, sql, params

    def test_first_page_preserves_newest_first_order(
        self,
    ):
        rows = [
            {
                "operation_id": "op-003",
                "completed_at": datetime(
                    2026,
                    9,
                    29,
                    1,
                    3,
                    tzinfo=timezone.utc,
                ),
            },
            {
                "operation_id": "op-002",
                "completed_at": datetime(
                    2026,
                    9,
                    29,
                    1,
                    2,
                    tzinfo=timezone.utc,
                ),
            },
        ]

        result, sql, params = self._read(
            rows,
            limit=2,
        )

        self.assertEqual(
            result,
            rows,
        )
        self.assertIn(
            "ORDER BY completed_at DESC, operation_id DESC",
            sql,
        )
        self.assertNotIn(
            "completed_at IS NULL",
            sql,
        )
        self.assertEqual(
            params,
            (2,),
        )

    def test_dated_cursor_uses_composite_keyset_boundary(
        self,
    ):
        completed_at = datetime(
            2026,
            9,
            29,
            1,
            2,
            tzinfo=timezone.utc,
        )

        self._read(
            [],
            limit=25,
            after_completed_at=completed_at,
            after_operation_id="op-002",
        )

        _, sql, params = self._read(
            [],
            limit=25,
            after_completed_at=completed_at,
            after_operation_id="op-002",
        )

        self.assertIn(
            "(completed_at, operation_id) < (%s, %s)",
            sql,
        )
        self.assertIn(
            "completed_at IS NOT NULL",
            sql,
        )
        self.assertEqual(
            params,
            (
                completed_at,
                "op-002",
                25,
            ),
        )

    def test_null_phase_is_deterministic_and_cursorable(
        self,
    ):
        _, sql, params = self._read(
            [],
            limit=10,
            include_null_completed_at=True,
        )

        self.assertIn(
            "completed_at IS NULL",
            sql,
        )
        self.assertIn(
            "ORDER BY operation_id DESC",
            sql,
        )
        self.assertEqual(
            params,
            (10,),
        )

        _, sql, params = self._read(
            [],
            limit=10,
            include_null_completed_at=True,
            after_operation_id="op-legacy-050",
        )

        self.assertIn(
            "completed_at IS NULL",
            sql,
        )
        self.assertIn(
            "operation_id < %s",
            sql,
        )
        self.assertIn(
            "ORDER BY operation_id DESC",
            sql,
        )
        self.assertEqual(
            params,
            (
                "op-legacy-050",
                10,
            ),
        )

    def test_cursor_arguments_fail_closed(
        self,
    ):
        completed_at = datetime(
            2026,
            9,
            29,
            1,
            2,
            tzinfo=timezone.utc,
        )

        with self.assertRaises(ValueError):
            repo.list_successful_blockchain_install_results(
                after_completed_at=completed_at,
            )

        with self.assertRaises(ValueError):
            repo.list_successful_blockchain_install_results(
                after_operation_id="op-002",
            )

        with self.assertRaises(ValueError):
            repo.list_successful_blockchain_install_results(
                include_null_completed_at=True,
                after_completed_at=completed_at,
                after_operation_id="op-002",
            )

    def test_limit_remains_bounded(
        self,
    ):
        _, _, params = self._read(
            [],
            limit=5000,
        )

        self.assertEqual(
            params,
            (500,),
        )

        with self.assertRaises(ValueError):
            repo.list_successful_blockchain_install_results(
                limit=0,
            )


    def test_success_reader_excludes_blank_operation_id_checkpoint_keys(self):
        from pathlib import Path

        source = Path(
            "backend/db/repositories/change_execution_repository.py"
        ).read_text()

        assert (
            "BTRIM(operation_id) <> ''" in source
            or "operation_id <> ''" in source
        ), (
            "successful blockchain.install reconciliation reader must exclude "
            "blank operation_id values because they cannot be persisted as "
            "durable reconciliation cursor keys"
        )

if __name__ == "__main__":
    unittest.main()
