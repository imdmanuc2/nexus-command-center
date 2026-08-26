BEGIN;

CREATE TABLE IF NOT EXISTS nexus.asset_instance_memberships (
    asset_id TEXT NOT NULL
        REFERENCES nexus.assets(asset_id)
        ON DELETE CASCADE,

    instance_id TEXT NOT NULL
        REFERENCES nexus.nexus_instances(instance_id)
        ON DELETE CASCADE,

    relationship_role TEXT NOT NULL DEFAULT 'observer'
        CHECK (
            relationship_role IN (
                'observer',
                'management-authority'
            )
        ),

    discovery_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    management_enabled BOOLEAN NOT NULL DEFAULT FALSE,

    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ,

    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (asset_id, instance_id),

    CHECK (
        relationship_role <> 'management-authority'
        OR management_enabled = TRUE
    )
);

CREATE INDEX IF NOT EXISTS idx_asset_instance_memberships_instance
    ON nexus.asset_instance_memberships(instance_id);

CREATE INDEX IF NOT EXISTS idx_asset_instance_memberships_role
    ON nexus.asset_instance_memberships(relationship_role);

CREATE UNIQUE INDEX IF NOT EXISTS uq_asset_single_management_authority
    ON nexus.asset_instance_memberships(asset_id)
    WHERE relationship_role = 'management-authority';

ALTER TABLE nexus.observations
    ADD COLUMN IF NOT EXISTS nexus_instance_id TEXT
    REFERENCES nexus.nexus_instances(instance_id)
    ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_observations_nexus_instance
    ON nexus.observations(nexus_instance_id, observed_at DESC);

ALTER TABLE nexus.discovery_scans
    ADD COLUMN IF NOT EXISTS nexus_instance_id TEXT
    REFERENCES nexus.nexus_instances(instance_id)
    ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_discovery_scans_nexus_instance
    ON nexus.discovery_scans(nexus_instance_id, created_at DESC);

INSERT INTO schema_migrations(version, description)
VALUES (
    '041',
    'Nexus asset observation and management authority foundation'
)
ON CONFLICT(version) DO NOTHING;

COMMIT;
