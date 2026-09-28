BEGIN;

-- Nexus Operations compatibility repair.
--
-- change_execution_repository.finish_failure() and
-- finish_cancelled() persist the terminal step failure/cancellation
-- reason in nexus.change_steps.error_message.
--
-- The original change_steps definition in migration 034 did not
-- include that column.
--
-- ADD COLUMN IF NOT EXISTS is intentional because an interrupted
-- application of this migration may have materialized the column
-- before its canonical schema_migrations ledger record was written.

ALTER TABLE nexus.change_steps
    ADD COLUMN IF NOT EXISTS error_message TEXT NOT NULL DEFAULT '';

COMMENT ON COLUMN nexus.change_steps.error_message IS
    'Terminal failure or cancellation reason recorded for a controlled change step.';

INSERT INTO public.schema_migrations (
    version,
    description
)
VALUES (
    '052',
    'Change step failure message compatibility'
)
ON CONFLICT (version) DO NOTHING;

COMMIT;
