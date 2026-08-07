BEGIN;
CREATE TABLE IF NOT EXISTS nexus.change_rollback_plans (
 rollback_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 change_id UUID NOT NULL REFERENCES nexus.change_requests(change_id) ON DELETE CASCADE,
 source_operation_id TEXT, rollback_action TEXT NOT NULL,
 target_type TEXT NOT NULL, target_id TEXT NOT NULL, asset_id TEXT,
 parameters JSONB NOT NULL DEFAULT '{}'::jsonb, reason TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'draft', approval_status TEXT NOT NULL DEFAULT 'pending',
 approved_by TEXT NOT NULL DEFAULT '', approved_at TIMESTAMPTZ,
 requested_by TEXT NOT NULL DEFAULT '', requested_at TIMESTAMPTZ,
 claimed_by TEXT NOT NULL DEFAULT '', lease_expires_at TIMESTAMPTZ,
 verification_status TEXT NOT NULL DEFAULT '', recovery_status TEXT NOT NULL DEFAULT '',
 result_data JSONB NOT NULL DEFAULT '{}'::jsonb, error_message TEXT NOT NULL DEFAULT '',
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 completed_at TIMESTAMPTZ,
 CONSTRAINT change_rollback_status_check CHECK (status IN ('draft','approved','queued','running','verifying','succeeded','failed','cancelled','manual_intervention')),
 CONSTRAINT change_rollback_approval_check CHECK (approval_status IN ('pending','approved','rejected','not_required'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_change_rollback_one_active ON nexus.change_rollback_plans(change_id) WHERE status IN ('draft','approved','queued','running','verifying');
CREATE INDEX IF NOT EXISTS idx_change_rollback_claim ON nexus.change_rollback_plans(status,approval_status,created_at);
CREATE TABLE IF NOT EXISTS nexus.change_rollback_attempts (
 attempt_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 rollback_id UUID NOT NULL REFERENCES nexus.change_rollback_plans(rollback_id) ON DELETE CASCADE,
 worker_id TEXT NOT NULL, attempt_number INTEGER NOT NULL DEFAULT 1,
 status TEXT NOT NULL DEFAULT 'running', capability TEXT NOT NULL,
 transport TEXT NOT NULL DEFAULT '', started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 completed_at TIMESTAMPTZ, duration_ms INTEGER, exit_code INTEGER,
 timed_out BOOLEAN NOT NULL DEFAULT FALSE, stdout TEXT NOT NULL DEFAULT '', stderr TEXT NOT NULL DEFAULT '',
 verification_data JSONB NOT NULL DEFAULT '{}'::jsonb, result_data JSONB NOT NULL DEFAULT '{}'::jsonb,
 error_message TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_change_rollback_attempts_plan ON nexus.change_rollback_attempts(rollback_id,started_at DESC);
CREATE TABLE IF NOT EXISTS nexus.change_rollback_events (
 event_id BIGSERIAL PRIMARY KEY,
 rollback_id UUID NOT NULL REFERENCES nexus.change_rollback_plans(rollback_id) ON DELETE CASCADE,
 event_type TEXT NOT NULL, actor_type TEXT NOT NULL DEFAULT 'system', actor_id TEXT NOT NULL DEFAULT '',
 message TEXT NOT NULL DEFAULT '', event_data JSONB NOT NULL DEFAULT '{}'::jsonb,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_change_rollback_events_plan ON nexus.change_rollback_events(rollback_id,created_at DESC);
ALTER TABLE nexus.change_requests ADD COLUMN IF NOT EXISTS active_rollback_id UUID;
ALTER TABLE nexus.change_requests ADD COLUMN IF NOT EXISTS recovery_status TEXT NOT NULL DEFAULT '';
ALTER TABLE nexus.change_requests ADD COLUMN IF NOT EXISTS recovered_at TIMESTAMPTZ;
COMMIT;
