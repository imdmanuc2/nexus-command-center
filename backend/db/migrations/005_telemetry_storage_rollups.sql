BEGIN;
CREATE SCHEMA IF NOT EXISTS nexus;

CREATE TABLE IF NOT EXISTS nexus.metric_samples (
    sample_id BIGSERIAL PRIMARY KEY,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value DOUBLE PRECISION NOT NULL,
    metric_unit TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'nexus-telemetry',
    labels JSONB NOT NULL DEFAULT '{}'::JSONB,
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB
);
CREATE INDEX IF NOT EXISTS idx_metric_samples_entity_time
ON nexus.metric_samples(entity_type, entity_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_metric_samples_metric_time
ON nexus.metric_samples(metric_name, observed_at DESC);

CREATE TABLE IF NOT EXISTS nexus.metric_current (
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value DOUBLE PRECISION NOT NULL,
    metric_unit TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'nexus-telemetry',
    labels JSONB NOT NULL DEFAULT '{}'::JSONB,
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    observed_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY(entity_type, entity_id, metric_name)
);

CREATE TABLE IF NOT EXISTS nexus.metric_rollups (
    bucket_start TIMESTAMPTZ NOT NULL,
    bucket_size TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_unit TEXT NOT NULL DEFAULT '',
    sample_count BIGINT NOT NULL,
    minimum_value DOUBLE PRECISION,
    maximum_value DOUBLE PRECISION,
    average_value DOUBLE PRECISION,
    sum_value DOUBLE PRECISION,
    last_value DOUBLE PRECISION,
    labels JSONB NOT NULL DEFAULT '{}'::JSONB,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY(bucket_start,bucket_size,entity_type,entity_id,metric_name)
);
CREATE INDEX IF NOT EXISTS idx_metric_rollups_lookup
ON nexus.metric_rollups(bucket_size,entity_type,entity_id,metric_name,bucket_start DESC);

CREATE TABLE IF NOT EXISTS nexus.telemetry_collector_state (
    collector_name TEXT PRIMARY KEY,
    last_started_at TIMESTAMPTZ,
    last_completed_at TIMESTAMPTZ,
    last_status TEXT NOT NULL DEFAULT 'never-run',
    last_error TEXT NOT NULL DEFAULT '',
    sample_count BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO public.schema_migrations(version, description)
VALUES ('005','Generic telemetry samples, current metrics, rollups, and collector state')
ON CONFLICT(version) DO NOTHING;
COMMIT;
