BEGIN;

ALTER TABLE nexus.nexus_peer_enrollments
    ADD COLUMN IF NOT EXISTS request_id TEXT;

ALTER TABLE nexus.nexus_peer_enrollments
    DROP CONSTRAINT IF EXISTS
        nexus_peer_enrollments_request_id_nonempty_check;

ALTER TABLE nexus.nexus_peer_enrollments
    ADD CONSTRAINT
        nexus_peer_enrollments_request_id_nonempty_check
    CHECK (
        request_id IS NULL
        OR char_length(btrim(request_id)) > 0
    );

CREATE UNIQUE INDEX IF NOT EXISTS
    uq_nexus_peer_enrollments_request_identity
    ON nexus.nexus_peer_enrollments (
        local_instance_id,
        requested_remote_instance_id,
        request_id
    )
    WHERE
        requested_remote_instance_id IS NOT NULL
        AND request_id IS NOT NULL;

INSERT INTO public.schema_migrations (
    version,
    description
)
VALUES (
    '048',
    'Nexus peer enrollment idempotency foundation'
)
ON CONFLICT(version) DO NOTHING;

COMMIT;
