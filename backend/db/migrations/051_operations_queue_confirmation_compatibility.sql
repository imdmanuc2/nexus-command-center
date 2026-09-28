BEGIN;

-- Compatibility repair for Nexus deployments whose durable Operations
-- queue was materialized from the Package 046 / migration 035 fallback
-- schema rather than the earlier migration 004 schema.
--
-- Current Change Management queue writers and blockchain.install
-- execution authority require confirmation actor and timestamp evidence.
--
-- This migration intentionally does not replay migration 004 and does
-- not alter the existing queue's retry, progress, leasing, or event
-- schema.

ALTER TABLE nexus.operation_queue
    ADD COLUMN IF NOT EXISTS confirmed_by TEXT NOT NULL DEFAULT '';

ALTER TABLE nexus.operation_queue
    ADD COLUMN IF NOT EXISTS confirmed_at TIMESTAMPTZ;

COMMENT ON COLUMN nexus.operation_queue.confirmed_by IS
    'Operator or authority that confirmed execution of a confirmation-required operation.';

COMMENT ON COLUMN nexus.operation_queue.confirmed_at IS
    'Timestamp when execution confirmation was recorded.';

INSERT INTO public.schema_migrations (
    version,
    description
)
VALUES (
    '051',
    'Operations queue execution confirmation compatibility'
)
ON CONFLICT (version) DO NOTHING;

COMMIT;
