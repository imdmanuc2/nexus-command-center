BEGIN;

CREATE TABLE IF NOT EXISTS nexus.operation_sessions (
    session_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE REFERENCES nexus.automation_runs(run_id) ON DELETE CASCADE,
    action_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    current_stage TEXT NOT NULL DEFAULT 'queued',
    progress_percent INTEGER NOT NULL DEFAULT 0 CHECK (progress_percent BETWEEN 0 AND 100),
    summary TEXT NOT NULL DEFAULT '',
    requested_by TEXT NOT NULL DEFAULT 'operator',
    correlation_id TEXT NOT NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nexus.operation_session_events (
    event_id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES nexus.operation_sessions(session_id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    stage TEXT NOT NULL,
    level TEXT NOT NULL DEFAULT 'info',
    message TEXT NOT NULL,
    progress_percent INTEGER CHECK (progress_percent BETWEEN 0 AND 100),
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_operation_session_events_session
    ON nexus.operation_session_events(session_id, event_id);
CREATE INDEX IF NOT EXISTS idx_operation_sessions_updated
    ON nexus.operation_sessions(updated_at DESC);

INSERT INTO nexus.schema_migrations(version, description)
VALUES ('020', 'Live operations console sessions and structured events')
ON CONFLICT (version) DO NOTHING;

COMMIT;
