BEGIN;

CREATE SCHEMA IF NOT EXISTS nexus;

CREATE TABLE IF NOT EXISTS nexus.platform_events (
    event_id BIGSERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'info',
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL DEFAULT '',
    previous_state JSONB NOT NULL DEFAULT '{}'::JSONB,
    current_state JSONB NOT NULL DEFAULT '{}'::JSONB,
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    source TEXT NOT NULL DEFAULT 'nexus-event-engine',
    correlation_id TEXT NOT NULL DEFAULT '',
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_platform_events_entity_time
ON nexus.platform_events(entity_type, entity_id, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_platform_events_type_time
ON nexus.platform_events(event_type, occurred_at DESC);

CREATE TABLE IF NOT EXISTS nexus.resource_state_snapshots (
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    state_hash TEXT NOT NULL,
    state_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
    first_observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (entity_type, entity_id)
);

CREATE TABLE IF NOT EXISTS nexus.event_engine_state (
    engine_name TEXT PRIMARY KEY,
    last_started_at TIMESTAMPTZ,
    last_completed_at TIMESTAMPTZ,
    last_status TEXT NOT NULL DEFAULT 'never-run',
    last_error TEXT NOT NULL DEFAULT '',
    evaluated_entities INTEGER NOT NULL DEFAULT 0,
    emitted_events INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO public.schema_migrations(version, description)
VALUES ('007', 'Platform state transition and event engine')
ON CONFLICT (version) DO NOTHING;

COMMIT;
