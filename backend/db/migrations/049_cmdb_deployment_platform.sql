BEGIN;

ALTER TABLE nexus.assets
    ADD COLUMN IF NOT EXISTS deployment_platform_id TEXT;

COMMENT ON COLUMN nexus.assets.deployment_platform_id IS
    'Explicit reviewed Seymour deployment platform profile identifier. '
    'NULL or blank means unclassified and not deployable.';

INSERT INTO schema_migrations (
    version,
    description
)
VALUES (
    '049',
    'CMDB deployment platform classification'
)
ON CONFLICT (version) DO NOTHING;

COMMIT;
