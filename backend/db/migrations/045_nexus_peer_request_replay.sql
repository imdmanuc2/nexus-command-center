BEGIN;

CREATE TABLE IF NOT EXISTS nexus.nexus_peer_request_nonces (
    local_instance_id TEXT NOT NULL
        REFERENCES nexus.nexus_instances(instance_id)
        ON DELETE CASCADE,

    remote_instance_id TEXT NOT NULL,

    nonce TEXT NOT NULL,

    request_timestamp TIMESTAMPTZ NOT NULL,

    expires_at TIMESTAMPTZ NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (
        local_instance_id,
        remote_instance_id,
        nonce
    ),

    CHECK (char_length(nonce) = 43),

    CHECK (expires_at > request_timestamp)
);

CREATE INDEX IF NOT EXISTS
    idx_nexus_peer_request_nonces_expiry
    ON nexus.nexus_peer_request_nonces(expires_at);

INSERT INTO public.schema_migrations (
    version,
    description
)
VALUES (
    '045',
    'Nexus peer signed-request replay protection'
)
ON CONFLICT(version) DO NOTHING;

COMMIT;
