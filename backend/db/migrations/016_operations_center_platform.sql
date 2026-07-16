
BEGIN;

CREATE SCHEMA IF NOT EXISTS nexus;

CREATE TABLE IF NOT EXISTS nexus.operations_center_snapshots (
    snapshot_id BIGSERIAL PRIMARY KEY,
    snapshot_key TEXT NOT NULL,
    health_score NUMERIC(6,2) NOT NULL DEFAULT 100,
    overall_status TEXT NOT NULL DEFAULT 'healthy',
    payload JSONB NOT NULL DEFAULT '{}'::JSONB,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_operations_center_snapshots_key_time
ON nexus.operations_center_snapshots(snapshot_key, generated_at DESC);

CREATE TABLE IF NOT EXISTS nexus.operations_center_state (
    state_key TEXT PRIMARY KEY,
    last_generated_at TIMESTAMPTZ,
    last_status TEXT NOT NULL DEFAULT 'never-run',
    last_error TEXT NOT NULL DEFAULT '',
    health_score NUMERIC(6,2) NOT NULL DEFAULT 100,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO public.schema_migrations(version, description)
VALUES ('016', 'Operations Center Platform layer')
ON CONFLICT (version) DO NOTHING;

COMMIT;
