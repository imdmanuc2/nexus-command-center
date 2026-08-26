BEGIN;

CREATE TABLE IF NOT EXISTS nexus.organizations (
    organization_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_organizations_status
    ON nexus.organizations(status);

ALTER TABLE nexus.sites
    ADD COLUMN IF NOT EXISTS organization_id TEXT
    REFERENCES nexus.organizations(organization_id)
    ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_sites_organization
    ON nexus.sites(organization_id);

CREATE TABLE IF NOT EXISTS nexus.nexus_instances (
    instance_id TEXT PRIMARY KEY,

    organization_id TEXT
        REFERENCES nexus.organizations(organization_id)
        ON DELETE SET NULL,

    site_id TEXT
        REFERENCES nexus.sites(site_id)
        ON DELETE SET NULL,

    name TEXT NOT NULL,
    hostname TEXT NOT NULL DEFAULT '',

    instance_role TEXT NOT NULL DEFAULT 'site-controller',
    status TEXT NOT NULL DEFAULT 'active',

    is_local BOOLEAN NOT NULL DEFAULT FALSE,
    federation_enabled BOOLEAN NOT NULL DEFAULT FALSE,

    api_base_url TEXT NOT NULL DEFAULT '',
    software_version TEXT NOT NULL DEFAULT '',

    last_seen_at TIMESTAMPTZ,

    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_nexus_instances_organization
    ON nexus.nexus_instances(organization_id);

CREATE INDEX IF NOT EXISTS idx_nexus_instances_site
    ON nexus.nexus_instances(site_id);

CREATE INDEX IF NOT EXISTS idx_nexus_instances_status
    ON nexus.nexus_instances(status);

CREATE UNIQUE INDEX IF NOT EXISTS uq_nexus_instances_local
    ON nexus.nexus_instances(is_local)
    WHERE is_local = TRUE;

INSERT INTO schema_migrations(version, description)
VALUES (
    '040',
    'Organization and Nexus instance identity foundation'
)
ON CONFLICT(version) DO NOTHING;

COMMIT;
