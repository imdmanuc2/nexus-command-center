BEGIN;

ALTER TABLE nexus.operation_queue
    ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ;

COMMENT ON COLUMN nexus.operation_queue.cancelled_at IS
    'Timestamp when the owning Operations worker finalized a requested cancellation.';

INSERT INTO public.schema_migrations (
    version,
    description
)
VALUES (
    '050',
    'Operations queue cancellation finalization compatibility'
)
ON CONFLICT (version) DO NOTHING;

COMMIT;
