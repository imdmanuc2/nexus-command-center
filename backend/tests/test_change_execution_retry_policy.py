import unittest
from unittest.mock import MagicMock

from backend.db.repositories import change_execution_repository as repo


def _connection_with_columns(*columns):
    conn = MagicMock()
    cur = MagicMock()

    conn.cursor.return_value.__enter__.return_value = cur
    cur.fetchall.return_value = [
        {"column_name": column}
        for column in columns
    ]

    return conn, cur


class ChangeExecutionRetryPolicyTests(unittest.TestCase):
    def test_attempt_limit_prefers_canonical_maximum_attempts(self):
        conn, cur = _connection_with_columns(
            "maximum_attempts",
            "max_attempts",
        )

        self.assertEqual(
            repo._attempt_limit_column(conn),
            "maximum_attempts",
        )

        sql = cur.execute.call_args.args[0]

        self.assertIn(
            "information_schema.columns",
            sql,
        )
        self.assertIn("maximum_attempts", sql)
        self.assertIn("max_attempts", sql)

    def test_attempt_limit_supports_original_operations_queue_schema(self):
        conn, _ = _connection_with_columns(
            "maximum_attempts",
        )

        self.assertEqual(
            repo._attempt_limit_column(conn),
            "maximum_attempts",
        )

    def test_attempt_limit_supports_change_execution_fallback_schema(self):
        conn, _ = _connection_with_columns(
            "max_attempts",
        )

        self.assertEqual(
            repo._attempt_limit_column(conn),
            "max_attempts",
        )

    def test_attempt_limit_fails_closed_when_neither_column_exists(self):
        conn, _ = _connection_with_columns()

        with self.assertRaisesRegex(
            RuntimeError,
            "attempt-limit column is unavailable",
        ):
            repo._attempt_limit_column(conn)

    def test_attempt_limit_never_returns_unreviewed_identifier(self):
        cases = (
            ("maximum_attempts",),
            ("max_attempts",),
            ("maximum_attempts", "max_attempts"),
        )

        for columns in cases:
            conn, _ = _connection_with_columns(
                *columns
            )

            self.assertIn(
                repo._attempt_limit_column(conn),
                {
                    "maximum_attempts",
                    "max_attempts",
                },
            )


if __name__ == "__main__":
    unittest.main()
