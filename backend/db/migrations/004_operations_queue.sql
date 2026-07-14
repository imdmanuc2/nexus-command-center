BEGIN;

-- ============================================================
-- OPERATIONS QUEUE
--
-- Provides durable execution for:
--   - queued operational playbooks
--   - scheduled operations
--   - bulk operations
--   - retries
--   - cancellation
--   - concurrency control
--   - worker leasing
--   - progress reporting
--
-- Browser pages never execute scripts directly. They submit
-- actions to the shared Operations Engine, which creates and
-- processes queue records.
-- ============================================================

CREATE TABLE IF NOT EXISTS nexus.operation_queue (
    operation_id             TEXT PRIMARY KEY,

    -- Shared Operations Engine action name:
    -- bitcoin.rpc.test
    -- miningcore.pool.readiness
    -- miner.asic.diagnostics
    -- bitcoin.service.restart
    action_name              TEXT NOT NULL,

    -- Canonical target identity.
    target_type              TEXT NOT NULL,
    target_id                TEXT NOT NULL,

    -- Optional CMDB enrichment.
    asset_id                 TEXT
                             REFERENCES nexus.assets(asset_id)
                             ON DELETE SET NULL,

    -- Optional registered playbook definition.
    playbook_id              TEXT
                             REFERENCES nexus.playbooks(playbook_id)
                             ON DELETE SET NULL,

    -- Created playbook run, once execution begins.
    run_id                   TEXT
                             REFERENCES nexus.playbook_runs(run_id)
                             ON DELETE SET NULL,

    -- pending, queued, running, succeeded, warning,
    -- failed, cancelled, expired
    status                   TEXT NOT NULL DEFAULT 'pending',

    -- Lower number means greater priority.
    -- 10 = emergency
    -- 50 = normal
    -- 90 = background
    priority                 INTEGER NOT NULL DEFAULT 50,

    -- Used to group bulk actions or related operations.
    batch_id                 TEXT NOT NULL DEFAULT '',
    correlation_id           TEXT NOT NULL,

    -- Prevents accidental duplicate submissions.
    idempotency_key          TEXT NOT NULL DEFAULT '',

    -- Operator, automation, scheduler, API, AI, system.
    triggered_by_type        TEXT NOT NULL DEFAULT 'operator',
    triggered_by_id          TEXT NOT NULL DEFAULT '',

    read_only                BOOLEAN NOT NULL DEFAULT TRUE,
    confirmation_required    BOOLEAN NOT NULL DEFAULT FALSE,
    confirmed                BOOLEAN NOT NULL DEFAULT FALSE,
    confirmed_by             TEXT NOT NULL DEFAULT '',
    confirmed_at             TIMESTAMPTZ,

    -- Operation arguments. Never store passwords, wallet seeds,
    -- private keys, API tokens, or RPC credentials here.
    input_data               JSONB NOT NULL DEFAULT '{}'::JSONB,

    -- Current execution output or final result.
    result_data              JSONB NOT NULL DEFAULT '{}'::JSONB,

    summary                  TEXT NOT NULL DEFAULT '',
    error_code               TEXT NOT NULL DEFAULT '',
    error_message            TEXT NOT NULL DEFAULT '',

    -- Progress range: 0.00 through 100.00.
    progress_percent         NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    current_step             INTEGER NOT NULL DEFAULT 0,
    total_steps              INTEGER NOT NULL DEFAULT 0,

    -- Retry policy.
    attempt_count            INTEGER NOT NULL DEFAULT 0,
    maximum_attempts         INTEGER NOT NULL DEFAULT 1,
    retry_delay_seconds      INTEGER NOT NULL DEFAULT 30,
    next_attempt_at          TIMESTAMPTZ,

    -- Execution timeout.
    timeout_seconds          INTEGER NOT NULL DEFAULT 300,

    -- Queue scheduling.
    scheduled_for            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at               TIMESTAMPTZ,

    -- Worker leasing prevents two executors from running
    -- the same operation simultaneously.
    lease_owner              TEXT NOT NULL DEFAULT '',
    lease_acquired_at        TIMESTAMPTZ,
    lease_expires_at         TIMESTAMPTZ,
    heartbeat_at             TIMESTAMPTZ,

    cancellation_requested   BOOLEAN NOT NULL DEFAULT FALSE,
    cancellation_reason      TEXT NOT NULL DEFAULT '',
    cancelled_by             TEXT NOT NULL DEFAULT '',
    cancelled_at             TIMESTAMPTZ,

    queued_at                TIMESTAMPTZ,
    started_at               TIMESTAMPTZ,
    completed_at             TIMESTAMPTZ,

    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_operation_priority
        CHECK (priority >= 0 AND priority <= 100),

    CONSTRAINT chk_operation_progress
        CHECK (
            progress_percent >= 0.00
            AND progress_percent <= 100.00
        ),

    CONSTRAINT chk_operation_attempts
        CHECK (
            attempt_count >= 0
            AND maximum_attempts >= 1
        ),

    CONSTRAINT chk_operation_steps
        CHECK (
            current_step >= 0
            AND total_steps >= 0
        ),

    CONSTRAINT chk_operation_timeout
        CHECK (timeout_seconds > 0)
);

-- Find executable work quickly.
CREATE INDEX IF NOT EXISTS idx_operation_queue_ready
    ON nexus.operation_queue(
        priority,
        scheduled_for,
        created_at
    )
    WHERE status IN ('pending', 'queued');

-- Operations currently running.
CREATE INDEX IF NOT EXISTS idx_operation_queue_running
    ON nexus.operation_queue(
        lease_expires_at,
        heartbeat_at
    )
    WHERE status = 'running';

-- Find operations for a specific target.
CREATE INDEX IF NOT EXISTS idx_operation_queue_target
    ON nexus.operation_queue(
        target_type,
        target_id,
        created_at DESC
    );

-- Find operations by action.
CREATE INDEX IF NOT EXISTS idx_operation_queue_action
    ON nexus.operation_queue(
        action_name,
        created_at DESC
    );

-- Bulk operation lookup.
CREATE INDEX IF NOT EXISTS idx_operation_queue_batch
    ON nexus.operation_queue(
        batch_id,
        created_at
    )
    WHERE batch_id <> '';

-- Correlate operations with events, audits, and playbook runs.
CREATE INDEX IF NOT EXISTS idx_operation_queue_correlation
    ON nexus.operation_queue(
        correlation_id,
        created_at DESC
    );

-- Retry scheduler.
CREATE INDEX IF NOT EXISTS idx_operation_queue_retry
    ON nexus.operation_queue(
        next_attempt_at,
        priority
    )
    WHERE status = 'failed'
      AND attempt_count < maximum_attempts;

-- Prevent duplicate operation submissions when an
-- idempotency key is supplied.
CREATE UNIQUE INDEX IF NOT EXISTS uq_operation_queue_idempotency
    ON nexus.operation_queue(idempotency_key)
    WHERE idempotency_key <> '';

-- Useful for CMDB asset history.
CREATE INDEX IF NOT EXISTS idx_operation_queue_asset
    ON nexus.operation_queue(
        asset_id,
        created_at DESC
    )
    WHERE asset_id IS NOT NULL;

-- ============================================================
-- OPERATION QUEUE EVENTS
--
-- Append-only lifecycle events for each queued operation.
-- Examples:
--   submitted
--   confirmed
--   queued
--   leased
--   started
--   progress
--   retry_scheduled
--   cancellation_requested
--   completed
--   failed
-- ============================================================

CREATE TABLE IF NOT EXISTS nexus.operation_queue_events (
    queue_event_id          BIGSERIAL PRIMARY KEY,

    operation_id            TEXT NOT NULL
                            REFERENCES nexus.operation_queue(operation_id)
                            ON DELETE CASCADE,

    event_type              TEXT NOT NULL,
    status                  TEXT NOT NULL DEFAULT '',

    message                 TEXT NOT NULL DEFAULT '',

    progress_percent        NUMERIC(5,2),
    step_number             INTEGER,
    step_name               TEXT NOT NULL DEFAULT '',

    actor_type              TEXT NOT NULL DEFAULT 'system',
    actor_id                TEXT NOT NULL DEFAULT 'nexus',

    data                    JSONB NOT NULL DEFAULT '{}'::JSONB,

    occurred_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_queue_event_progress
        CHECK (
            progress_percent IS NULL
            OR (
                progress_percent >= 0.00
                AND progress_percent <= 100.00
            )
        ),

    CONSTRAINT chk_queue_event_step
        CHECK (
            step_number IS NULL
            OR step_number >= 0
        )
);

CREATE INDEX IF NOT EXISTS idx_operation_queue_events_operation
    ON nexus.operation_queue_events(
        operation_id,
        occurred_at
    );

CREATE INDEX IF NOT EXISTS idx_operation_queue_events_type
    ON nexus.operation_queue_events(
        event_type,
        occurred_at DESC
    );

-- ============================================================
-- OPERATION BATCHES
--
-- Represents one operator request targeting many systems.
-- Example:
--   Run ASIC Diagnostics against 500 miners.
-- ============================================================

CREATE TABLE IF NOT EXISTS nexus.operation_batches (
    batch_id                 TEXT PRIMARY KEY,

    name                     TEXT NOT NULL,
    description              TEXT NOT NULL DEFAULT '',

    action_name              TEXT NOT NULL,
    target_type              TEXT NOT NULL,

    status                   TEXT NOT NULL DEFAULT 'pending',

    triggered_by_type        TEXT NOT NULL DEFAULT 'operator',
    triggered_by_id          TEXT NOT NULL DEFAULT '',

    correlation_id           TEXT NOT NULL,

    total_operations         INTEGER NOT NULL DEFAULT 0,
    pending_operations       INTEGER NOT NULL DEFAULT 0,
    running_operations       INTEGER NOT NULL DEFAULT 0,
    succeeded_operations     INTEGER NOT NULL DEFAULT 0,
    warning_operations       INTEGER NOT NULL DEFAULT 0,
    failed_operations        INTEGER NOT NULL DEFAULT 0,
    cancelled_operations     INTEGER NOT NULL DEFAULT 0,

    maximum_concurrency      INTEGER NOT NULL DEFAULT 10,

    input_data               JSONB NOT NULL DEFAULT '{}'::JSONB,
    result_summary           JSONB NOT NULL DEFAULT '{}'::JSONB,

    scheduled_for            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at               TIMESTAMPTZ,
    completed_at             TIMESTAMPTZ,

    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_operation_batch_counts
        CHECK (
            total_operations >= 0
            AND pending_operations >= 0
            AND running_operations >= 0
            AND succeeded_operations >= 0
            AND warning_operations >= 0
            AND failed_operations >= 0
            AND cancelled_operations >= 0
        ),

    CONSTRAINT chk_operation_batch_concurrency
        CHECK (maximum_concurrency > 0)
);

CREATE INDEX IF NOT EXISTS idx_operation_batches_status
    ON nexus.operation_batches(
        status,
        scheduled_for,
        created_at
    );

CREATE INDEX IF NOT EXISTS idx_operation_batches_action
    ON nexus.operation_batches(
        action_name,
        created_at DESC
    );

CREATE INDEX IF NOT EXISTS idx_operation_batches_correlation
    ON nexus.operation_batches(correlation_id);


-- ============================================================
-- UPDATED-AT TRIGGER
-- ============================================================

CREATE OR REPLACE FUNCTION nexus.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_operation_queue_updated_at
    ON nexus.operation_queue;

CREATE TRIGGER trg_operation_queue_updated_at
BEFORE UPDATE ON nexus.operation_queue
FOR EACH ROW
EXECUTE FUNCTION nexus.set_updated_at();

DROP TRIGGER IF EXISTS trg_operation_batches_updated_at
    ON nexus.operation_batches;

CREATE TRIGGER trg_operation_batches_updated_at
BEFORE UPDATE ON nexus.operation_batches
FOR EACH ROW
EXECUTE FUNCTION nexus.set_updated_at();

-- ============================================================
-- COMMENTS / CONTRACT
-- ============================================================

COMMENT ON TABLE nexus.operation_queue IS
    'Durable shared Operations Engine queue used by every Nexus page.';

COMMENT ON COLUMN nexus.operation_queue.action_name IS
    'Registered shared operation such as bitcoin.rpc.test or miningcore.pool.readiness.';

COMMENT ON COLUMN nexus.operation_queue.target_type IS
    'Canonical target class such as asset, pool, worker, blockchain-node, server, or service.';

COMMENT ON COLUMN nexus.operation_queue.target_id IS
    'Canonical Nexus ID. Never use an IP address as durable identity.';

COMMENT ON COLUMN nexus.operation_queue.input_data IS
    'Operation parameters only. Credentials and private keys are forbidden.';

COMMENT ON COLUMN nexus.operation_queue.lease_owner IS
    'Executor currently responsible for processing the operation.';

COMMENT ON TABLE nexus.operation_queue_events IS
    'Append-only operation lifecycle and progress event stream.';

COMMENT ON TABLE nexus.operation_batches IS
    'Tracks one bulk operation request containing multiple queue records.';

-- ============================================================
-- MIGRATION RECORD
-- ============================================================

INSERT INTO schema_migrations (
    version,
    description
)
VALUES (
    '004',
    'Durable operations queue, queue events, bulk batches, leasing, retries, cancellation, and progress'
)
ON CONFLICT (version) DO NOTHING;

COMMIT;
