BEGIN;

CREATE TABLE IF NOT EXISTS nexus.nexus_peer_settings (
    instance_id TEXT PRIMARY KEY
        REFERENCES nexus.nexus_instances(instance_id)
        ON DELETE CASCADE,

    allow_peer_connections BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nexus.nexus_peers (
    peer_id TEXT PRIMARY KEY,

    local_instance_id TEXT NOT NULL
        REFERENCES nexus.nexus_instances(instance_id)
        ON DELETE CASCADE,

    remote_instance_id TEXT,

    organization_id TEXT,
    site_id TEXT,

    name TEXT NOT NULL DEFAULT '',
    hostname TEXT NOT NULL DEFAULT '',

    peer_base_url TEXT NOT NULL DEFAULT '',

    protocol_name TEXT NOT NULL DEFAULT 'seymour-nexus-peer',
    protocol_version TEXT NOT NULL DEFAULT '1',

    status TEXT NOT NULL DEFAULT 'configured'
        CHECK (
            status IN (
                'configured',
                'verified',
                'disabled',
                'unreachable'
            )
        ),

    enabled BOOLEAN NOT NULL DEFAULT FALSE,

    peer_awareness BOOLEAN NOT NULL DEFAULT TRUE,

    federation_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    cmdb_exchange_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    discovery_exchange_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    management_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    authority_delegation_enabled BOOLEAN NOT NULL DEFAULT FALSE,

    last_verified_at TIMESTAMPTZ,
    last_seen_at TIMESTAMPTZ,

    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (federation_enabled = FALSE),
    CHECK (cmdb_exchange_enabled = FALSE),
    CHECK (discovery_exchange_enabled = FALSE),
    CHECK (management_enabled = FALSE),
    CHECK (authority_delegation_enabled = FALSE)
);

CREATE INDEX IF NOT EXISTS idx_nexus_peers_local_instance
    ON nexus.nexus_peers(local_instance_id);

CREATE INDEX IF NOT EXISTS idx_nexus_peers_remote_instance
    ON nexus.nexus_peers(remote_instance_id);

CREATE INDEX IF NOT EXISTS idx_nexus_peers_status
    ON nexus.nexus_peers(status);

CREATE UNIQUE INDEX IF NOT EXISTS uq_nexus_peers_local_remote
    ON nexus.nexus_peers(local_instance_id, remote_instance_id)
    WHERE remote_instance_id IS NOT NULL;

INSERT INTO nexus.nexus_peer_settings (
    instance_id,
    allow_peer_connections
)
SELECT
    instance_id,
    FALSE
FROM nexus.nexus_instances
WHERE is_local = TRUE
ON CONFLICT (instance_id) DO NOTHING;

INSERT INTO schema_migrations(version, description)
VALUES (
    '042',
    'Nexus peer registry and connection settings foundation'
)
ON CONFLICT(version) DO NOTHING;

COMMIT;
