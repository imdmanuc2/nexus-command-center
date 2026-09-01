BEGIN;

CREATE TABLE IF NOT EXISTS nexus.nexus_peer_outbound_pairings (
    pairing_id TEXT PRIMARY KEY,

    local_instance_id TEXT NOT NULL
        REFERENCES nexus.nexus_instances(instance_id)
        ON DELETE CASCADE,

    remote_instance_id TEXT NOT NULL,

    remote_name TEXT NOT NULL DEFAULT '',
    remote_hostname TEXT NOT NULL DEFAULT '',

    peer_base_url TEXT NOT NULL DEFAULT '',

    remote_public_key_algorithm TEXT,
    remote_public_key TEXT,
    remote_public_key_fingerprint TEXT,

    remote_enrollment_id TEXT,

    status TEXT NOT NULL DEFAULT 'requesting'
        CHECK (
            status IN (
                'requesting',
                'pending',
                'approved',
                'rejected',
                'completing',
                'connected',
                'expired',
                'failed'
            )
        ),

    expires_at TIMESTAMPTZ,

    requested_at TIMESTAMPTZ,
    approved_at TIMESTAMPTZ,
    rejected_at TIMESTAMPTZ,
    connected_at TIMESTAMPTZ,

    last_error TEXT NOT NULL DEFAULT '',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (
        remote_public_key_algorithm IS NULL
        OR remote_public_key_algorithm = 'Ed25519'
    )
);

CREATE INDEX IF NOT EXISTS
    idx_nexus_peer_outbound_pairings_local
    ON nexus.nexus_peer_outbound_pairings(local_instance_id);

CREATE INDEX IF NOT EXISTS
    idx_nexus_peer_outbound_pairings_remote
    ON nexus.nexus_peer_outbound_pairings(remote_instance_id);

CREATE INDEX IF NOT EXISTS
    idx_nexus_peer_outbound_pairings_status
    ON nexus.nexus_peer_outbound_pairings(status);

CREATE UNIQUE INDEX IF NOT EXISTS
    uq_nexus_peer_outbound_pairings_active_remote
    ON nexus.nexus_peer_outbound_pairings(
        local_instance_id,
        remote_instance_id
    )
    WHERE status IN (
        'requesting',
        'pending',
        'approved',
        'completing'
    );

INSERT INTO public.schema_migrations (
    version,
    description
)
VALUES (
    '047',
    'Nexus outbound peer pairing state foundation'
)
ON CONFLICT(version) DO NOTHING;

COMMIT;
