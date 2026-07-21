BEGIN;

-- Package 046 owns the canonical durable execution queue when an earlier
-- package has not installed it. IF NOT EXISTS preserves existing deployments.
CREATE TABLE IF NOT EXISTS nexus.operation_queue (
    operation_id TEXT PRIMARY KEY,
    action_name TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    asset_id TEXT,
    status TEXT NOT NULL DEFAULT 'queued',
    priority INTEGER NOT NULL DEFAULT 100,
    correlation_id TEXT NOT NULL DEFAULT '',
    idempotency_key TEXT NOT NULL DEFAULT '',
    triggered_by_type TEXT NOT NULL DEFAULT 'system',
    triggered_by_id TEXT NOT NULL DEFAULT '',
    read_only BOOLEAN NOT NULL DEFAULT FALSE,
    confirmation_required BOOLEAN NOT NULL DEFAULT FALSE,
    confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    input_data JSONB NOT NULL DEFAULT '{}'::JSONB,
    result_data JSONB NOT NULL DEFAULT '{}'::JSONB,
    summary TEXT NOT NULL DEFAULT '',
    error_message TEXT NOT NULL DEFAULT '',
    timeout_seconds INTEGER NOT NULL DEFAULT 120,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 1,
    progress_percent INTEGER NOT NULL DEFAULT 0,
    current_step INTEGER NOT NULL DEFAULT 0,
    total_steps INTEGER NOT NULL DEFAULT 1,
    lease_owner TEXT NOT NULL DEFAULT '',
    lease_acquired_at TIMESTAMPTZ,
    lease_expires_at TIMESTAMPTZ,
    heartbeat_at TIMESTAMPTZ,
    scheduled_for TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    queued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    cancellation_requested BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_operation_queue_idempotency
    ON nexus.operation_queue(idempotency_key)
    WHERE idempotency_key <> '';

CREATE INDEX IF NOT EXISTS idx_operation_queue_claim
    ON nexus.operation_queue(status, priority, scheduled_for, created_at);

CREATE INDEX IF NOT EXISTS idx_operation_queue_lease
    ON nexus.operation_queue(status, lease_expires_at);

CREATE TABLE IF NOT EXISTS nexus.operation_queue_events (
    event_id BIGSERIAL PRIMARY KEY,
    operation_id TEXT NOT NULL
        REFERENCES nexus.operation_queue(operation_id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    actor_type TEXT NOT NULL DEFAULT 'system',
    actor_id TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL DEFAULT '',
    event_data JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_operation_queue_events_operation
    ON nexus.operation_queue_events(operation_id, created_at DESC);

CREATE TABLE IF NOT EXISTS nexus.change_execution_workers (
    worker_id TEXT PRIMARY KEY,
    hostname TEXT NOT NULL,
    process_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'starting',
    current_operation_id TEXT,
    last_heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    stopped_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB
);

CREATE TABLE IF NOT EXISTS nexus.change_execution_attempts (
    attempt_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    change_id UUID REFERENCES nexus.change_requests(change_id) ON DELETE CASCADE,
    operation_id TEXT NOT NULL,
    worker_id TEXT NOT NULL,
    attempt_number INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL,
    capability TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    transport TEXT NOT NULL DEFAULT '',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,
    exit_code INTEGER,
    timed_out BOOLEAN NOT NULL DEFAULT FALSE,
    stdout TEXT NOT NULL DEFAULT '',
    stderr TEXT NOT NULL DEFAULT '',
    result_data JSONB NOT NULL DEFAULT '{}'::JSONB,
    error_message TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_change_execution_attempts_change
    ON nexus.change_execution_attempts(change_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_change_execution_attempts_operation
    ON nexus.change_execution_attempts(operation_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_change_execution_workers_heartbeat
    ON nexus.change_execution_workers(last_heartbeat_at DESC);

ALTER TABLE nexus.change_requests
    ADD COLUMN IF NOT EXISTS execution_worker_id TEXT;
ALTER TABLE nexus.change_requests
    ADD COLUMN IF NOT EXISTS verification_status TEXT NOT NULL DEFAULT '';
ALTER TABLE nexus.change_requests
    ADD COLUMN IF NOT EXISTS rollback_status TEXT NOT NULL DEFAULT '';

COMMIT;
