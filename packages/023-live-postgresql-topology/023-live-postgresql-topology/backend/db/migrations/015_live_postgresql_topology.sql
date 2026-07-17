
BEGIN;

CREATE SCHEMA IF NOT EXISTS nexus;

CREATE TABLE IF NOT EXISTS nexus.topology_reconciliation_state (
    reconciler_name TEXT PRIMARY KEY,
    last_started_at TIMESTAMPTZ,
    last_completed_at TIMESTAMPTZ,
    last_status TEXT NOT NULL DEFAULT 'never-run',
    last_error TEXT NOT NULL DEFAULT '',
    relationships_written INTEGER NOT NULL DEFAULT 0,
    relationships_deactivated INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_relationships_active_topology
ON nexus.relationships(
    status,
    source_type,
    source_id,
    relationship_type,
    target_type,
    target_id
);

CREATE INDEX IF NOT EXISTS idx_relationships_reconciler_source
ON nexus.relationships(source, status, updated_at DESC);

INSERT INTO public.schema_migrations(version, description)
VALUES ('015', 'Live PostgreSQL topology reconciliation')
ON CONFLICT (version) DO NOTHING;

COMMIT;
