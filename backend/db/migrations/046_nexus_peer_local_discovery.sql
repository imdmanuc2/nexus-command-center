BEGIN;

ALTER TABLE nexus.nexus_peer_settings
    ADD COLUMN IF NOT EXISTS
        local_discovery_enabled BOOLEAN NOT NULL DEFAULT FALSE;

INSERT INTO public.schema_migrations (
    version,
    description
)
VALUES (
    '046',
    'Nexus local peer discovery permission foundation'
)
ON CONFLICT(version) DO NOTHING;

COMMIT;
