BEGIN;
CREATE SCHEMA IF NOT EXISTS nexus;

CREATE TABLE IF NOT EXISTS nexus.operations_timeline (
    timeline_id BIGSERIAL PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'info',
    entity_type TEXT NOT NULL DEFAULT '',
    entity_id TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    message TEXT NOT NULL DEFAULT '',
    data JSONB NOT NULL DEFAULT '{}'::JSONB,
    occurred_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_operations_timeline_source
ON nexus.operations_timeline(source_type, source_id);

CREATE INDEX IF NOT EXISTS idx_operations_timeline_occurred
ON nexus.operations_timeline(occurred_at DESC, timeline_id DESC);

CREATE INDEX IF NOT EXISTS idx_operations_timeline_entity
ON nexus.operations_timeline(entity_type, entity_id, occurred_at DESC);

CREATE TABLE IF NOT EXISTS nexus.asset_state_history (
    history_id BIGSERIAL PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    state_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
    state_hash TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_asset_state_history_snapshot
ON nexus.asset_state_history(entity_type, entity_id, state_hash);

CREATE TABLE IF NOT EXISTS nexus.operator_annotations (
    annotation_id BIGSERIAL PRIMARY KEY,
    entity_type TEXT NOT NULL DEFAULT '',
    entity_id TEXT NOT NULL DEFAULT '',
    annotation_type TEXT NOT NULL DEFAULT 'note',
    title TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT 'operator',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nexus.timeline_engine_state (
    engine_name TEXT PRIMARY KEY,
    last_platform_event_id BIGINT NOT NULL DEFAULT 0,
    last_alert_seen_at TIMESTAMPTZ,
    last_recommendation_seen_at TIMESTAMPTZ,
    last_automation_seen_at TIMESTAMPTZ,
    last_status TEXT NOT NULL DEFAULT 'never-run',
    last_error TEXT NOT NULL DEFAULT '',
    entries_written INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO public.schema_migrations(version, description)
VALUES ('012', 'Operations timeline and asset history')
ON CONFLICT (version) DO NOTHING;
COMMIT;
