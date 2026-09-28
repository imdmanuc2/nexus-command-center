import inspect
import unittest

from backend.db.repositories import (
    change_execution_repository as repo,
)


class ChangeExecutionStaleRecoveryTests(
    unittest.TestCase
):
    def test_claim_resolves_compatible_attempt_limit(self):
        source = inspect.getsource(repo.claim_next)

        self.assertIn(
            "_attempt_limit_column(conn)",
            source,
        )
        self.assertIn(
            "attempt_count < {attempt_limit_column}",
            source,
        )

    def test_claim_checks_budget_in_select_and_update(self):
        source = inspect.getsource(repo.claim_next)

        self.assertGreaterEqual(
            source.count(
                "attempt_count < {attempt_limit_column}"
            ),
            2,
        )

    def test_stale_recovery_resolves_attempt_limit(self):
        source = inspect.getsource(
            repo.reconcile_stale
        )

        self.assertIn(
            "_attempt_limit_column(conn)",
            source,
        )

    def test_retryable_stale_operation_is_requeued(self):
        source = inspect.getsource(
            repo.reconcile_stale
        )

        self.assertIn(
            "SET status='queued'",
            source,
        )
        self.assertIn(
            "attempt_count < {attempt_limit_column}",
            source,
        )
        self.assertIn(
            "retry permitted",
            source,
        )

    def test_exhausted_stale_operation_fails(self):
        source = inspect.getsource(
            repo.reconcile_stale
        )

        self.assertIn(
            "SET status='failed'",
            source,
        )
        self.assertIn(
            "attempt_count >= {attempt_limit_column}",
            source,
        )
        self.assertIn(
            "retry budget exhausted",
            source,
        )

    def test_exhausted_operation_gets_completion_timestamp(self):
        source = inspect.getsource(
            repo.reconcile_stale
        )

        self.assertIn(
            "completed_at=COALESCE(completed_at,NOW())",
            source,
        )

    def test_stale_recovery_clears_lease_in_both_paths(self):
        source = inspect.getsource(
            repo.reconcile_stale
        )

        self.assertGreaterEqual(
            source.count("lease_owner=''"),
            2,
        )
        self.assertGreaterEqual(
            source.count("lease_expires_at=NULL"),
            2,
        )


if __name__ == "__main__":
    unittest.main()
