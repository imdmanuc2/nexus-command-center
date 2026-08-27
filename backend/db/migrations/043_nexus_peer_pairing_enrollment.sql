BEGIN;

CREATE TABLE IF NOT EXISTS nexus.nexus_peer_enrollments (
    enrollment_id TEXT PRIMARY KEY,

    local_instance_id TEXT NOT NULL
        REFERENCES nexus.nexus_instances(instance_id)
        ON DELETE CASCADE,

    secret_hash TEXT NOT NULL,

    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (
            status IN (
                'pending',
                'approved',
                'rejected',
                'used',
                'expired'
            )
        ),

    requested_remote_instance_id TEXT,
    requested_remote_name TEXT NOT NULL DEFAULT '',
    requested_remote_hostname TEXT NOT NULL DEFAULT '',
    requested_peer_base_url TEXT NOT NULL DEFAULT '',

    expires_at TIMESTAMPTZ NOT NULL,

    approved_at TIMESTAMPTZ,
    rejected_at TIMESTAMPTZ,
    used_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (char_length(secret_hash) = 64)
);

CREATE INDEX IF NOT EXISTS idx_nexus_peer_enrollments_local
    ON nexus.nexus_peer_enrollments(local_instance_id);

CREATE INDEX IF NOT EXISTS idx_nexus_peer_enrollments_status
    ON nexus.nexus_peer_enrollments(status);

CREATE INDEX IF NOT EXISTS idx_nexus_peer_enrollments_expiry
    ON nexus.nexus_peer_enrollments(expires_at);

INSERT INTO public.schema_migrations (
    version,
    description
)
VALUES (
    '043',
    'Nexus peer pairing enrollment foundation'
)
ON CONFLICT(version) DO NOTHING;

COMMIT;
