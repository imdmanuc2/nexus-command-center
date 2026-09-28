from __future__ import annotations

import contextlib
import unittest
from unittest.mock import patch

from backend.core.operation_execution_control import (
    OperationLeaseLost,
)
from backend.db.repositories import (
    change_execution_repository as repo,
)


class FakeCursor:
    def __init__(
        self,
        *,
        terminal_authority=True,
    ):
        self.terminal_authority = (
            terminal_authority
        )
        self.executions = []
        self._fetchone = None

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        tb,
    ):
        return False

    def execute(
        self,
        sql,
        parameters=None,
    ):
        normalized = " ".join(
            str(sql).split()
        )

        self.executions.append(
            {
                "sql": normalized,
                "parameters": parameters,
            }
        )

        if (
            "UPDATE nexus.operation_queue"
            in normalized
            and "RETURNING operation_id"
            in normalized
        ):
            self._fetchone = (
                {"operation_id": "op-final-1"}
                if self.terminal_authority
                else None
            )
        else:
            self._fetchone = None

    def fetchone(self):
        value = self._fetchone
        self._fetchone = None
        return value


class FakeConnection:
    def __init__(
        self,
        *,
        terminal_authority=True,
    ):
        self.cursor_object = FakeCursor(
            terminal_authority=(
                terminal_authority
            )
        )

    def cursor(self):
        return self.cursor_object


class FakeTransaction:
    def __init__(
        self,
        *,
        terminal_authority=True,
    ):
        self.connection = FakeConnection(
            terminal_authority=(
                terminal_authority
            )
        )
        self.entered = False
        self.exited = False
        self.exception_type = None

    def __enter__(self):
        self.entered = True
        return self.connection

    def __exit__(
        self,
        exc_type,
        exc,
        tb,
    ):
        self.exited = True
        self.exception_type = exc_type

        # Real transaction context propagates the
        # exception so rollback semantics can occur.
        return False


class ChangeExecutionFinalizationTests(
    unittest.TestCase
):
    def operation(
        self,
        *,
        cancellation_requested=False,
    ):
        return {
            "operation_id": "op-final-1",
            "action_name": "blockchain.install",
            "cancellation_requested":
                cancellation_requested,
        }

    def change(self):
        return {
            "change_id": "chg-final-1",
            "operation_id": "op-final-1",
            "status": "executing",
        }

    def result(self):
        return {
            "status": "completed",
            "providerId": "bitcoin-mainnet",
            "storageTargetId": "storage-main",
            "steps": [],
        }

    @contextlib.contextmanager
    def transaction_patch(
        self,
        *,
        terminal_authority=True,
    ):
        fake = FakeTransaction(
            terminal_authority=(
                terminal_authority
            )
        )

        with patch.object(
            repo,
            "transaction",
            return_value=fake,
        ):
            yield fake

    @staticmethod
    def sql(fake):
        return [
            item["sql"]
            for item in (
                fake
                .connection
                .cursor_object
                .executions
            )
        ]

    def test_success_claims_authority_before_attempt_update(
        self,
    ):
        with self.transaction_patch() as fake:
            repo.finish_success(
                "attempt-final-1",
                self.operation(),
                self.change(),
                self.result(),
                "worker-final-1",
            )

        statements = self.sql(fake)

        self.assertGreaterEqual(
            len(statements),
            4,
        )

        self.assertIn(
            "UPDATE nexus.operation_queue",
            statements[0],
        )
        self.assertIn(
            "status='running'",
            statements[0],
        )
        self.assertIn(
            "lease_owner=%s",
            statements[0],
        )
        self.assertIn(
            "cancellation_requested=FALSE",
            statements[0],
        )
        self.assertIn(
            "RETURNING operation_id",
            statements[0],
        )

        self.assertIn(
            "UPDATE nexus.change_execution_attempts",
            statements[1],
        )

        self.assertIn(
            "status='running'",
            statements[1],
        )
        self.assertIn(
            "worker_id=%s",
            statements[1],
        )

    def test_failure_claims_authority_before_attempt_update(
        self,
    ):
        with self.transaction_patch() as fake:
            repo.finish_failure(
                "attempt-final-1",
                self.operation(),
                self.change(),
                "offline failure",
                {
                    "status": "failed",
                    "steps": [],
                },
                "worker-final-1",
            )

        statements = self.sql(fake)

        self.assertIn(
            "UPDATE nexus.operation_queue",
            statements[0],
        )
        self.assertIn(
            "status='failed'",
            statements[0],
        )
        self.assertIn(
            "cancellation_requested=FALSE",
            statements[0],
        )

        self.assertIn(
            "UPDATE nexus.change_execution_attempts",
            statements[1],
        )

        self.assertTrue(
            any(
                "UPDATE nexus.change_requests"
                in item
                and "status='failed'"
                in item
                for item in statements
            )
        )

    def test_cancel_requires_cancel_request_and_ownership(
        self,
    ):
        with self.transaction_patch() as fake:
            repo.finish_cancelled(
                "attempt-final-1",
                self.operation(
                    cancellation_requested=True
                ),
                self.change(),
                "worker-final-1",
                "Operator cancelled.",
            )

        statements = self.sql(fake)

        terminal = statements[0]

        self.assertIn(
            "UPDATE nexus.operation_queue",
            terminal,
        )
        self.assertIn(
            "status='cancelled'",
            terminal,
        )
        self.assertIn(
            "status='running'",
            terminal,
        )
        self.assertIn(
            "lease_owner=%s",
            terminal,
        )
        self.assertIn(
            "cancellation_requested=TRUE",
            terminal,
        )
        self.assertIn(
            "RETURNING operation_id",
            terminal,
        )

        self.assertTrue(
            any(
                "UPDATE nexus.change_requests"
                in item
                and "status='cancelled'"
                in item
                for item in statements
            )
        )

        self.assertTrue(
            any(
                "UPDATE nexus.change_steps"
                in item
                and "status='skipped'"
                in item
                for item in statements
            )
        )

    def test_success_lease_loss_stops_before_other_mutation(
        self,
    ):
        with self.transaction_patch(
            terminal_authority=False
        ) as fake:
            with self.assertRaises(
                OperationLeaseLost
            ):
                repo.finish_success(
                    "attempt-final-1",
                    self.operation(),
                    self.change(),
                    self.result(),
                    "worker-stale-1",
                )

        statements = self.sql(fake)

        self.assertEqual(
            len(statements),
            1,
        )
        self.assertIn(
            "UPDATE nexus.operation_queue",
            statements[0],
        )

        self.assertIs(
            fake.exception_type,
            OperationLeaseLost,
        )

    def test_failure_lease_loss_stops_before_other_mutation(
        self,
    ):
        with self.transaction_patch(
            terminal_authority=False
        ) as fake:
            with self.assertRaises(
                OperationLeaseLost
            ):
                repo.finish_failure(
                    "attempt-final-1",
                    self.operation(),
                    self.change(),
                    "stale worker failure",
                    {},
                    "worker-stale-1",
                )

        statements = self.sql(fake)

        self.assertEqual(
            len(statements),
            1,
        )

        self.assertIn(
            "UPDATE nexus.operation_queue",
            statements[0],
        )

    def test_cancel_lease_loss_stops_before_other_mutation(
        self,
    ):
        with self.transaction_patch(
            terminal_authority=False
        ) as fake:
            with self.assertRaises(
                OperationLeaseLost
            ):
                repo.finish_cancelled(
                    "attempt-final-1",
                    self.operation(
                        cancellation_requested=True
                    ),
                    self.change(),
                    "worker-stale-1",
                )

        statements = self.sql(fake)

        self.assertEqual(
            len(statements),
            1,
        )

        self.assertIn(
            "UPDATE nexus.operation_queue",
            statements[0],
        )

    def test_success_and_failure_do_not_win_over_cancellation(
        self,
    ):
        for finalizer in (
            "success",
            "failure",
        ):
            with self.subTest(
                finalizer=finalizer
            ):
                with self.transaction_patch(
                    terminal_authority=False
                ) as fake:
                    with self.assertRaises(
                        OperationLeaseLost
                    ):
                        if finalizer == "success":
                            repo.finish_success(
                                "attempt-final-1",
                                self.operation(
                                    cancellation_requested=True
                                ),
                                self.change(),
                                self.result(),
                                "worker-final-1",
                            )
                        else:
                            repo.finish_failure(
                                "attempt-final-1",
                                self.operation(
                                    cancellation_requested=True
                                ),
                                self.change(),
                                "failure after cancel request",
                                {},
                                "worker-final-1",
                            )

                statements = self.sql(fake)

                self.assertEqual(
                    len(statements),
                    1,
                )

                self.assertIn(
                    "cancellation_requested=FALSE",
                    statements[0],
                )


if __name__ == "__main__":
    unittest.main()
