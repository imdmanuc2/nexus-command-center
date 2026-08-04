BEGIN;

CREATE TABLE IF NOT EXISTS nexus.verification_profiles (
 profile_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 profile_key TEXT NOT NULL UNIQUE,
 name TEXT NOT NULL,
 description TEXT NOT NULL DEFAULT '',
 target_type TEXT NOT NULL DEFAULT 'asset',
 enabled BOOLEAN NOT NULL DEFAULT TRUE,
 rollback_on_failure BOOLEAN NOT NULL DEFAULT FALSE,
 minimum_score NUMERIC(5,2) NOT NULL DEFAULT 100.00,
 metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
 created_by TEXT NOT NULL DEFAULT 'nexus',
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 CHECK (minimum_score BETWEEN 0 AND 100)
);

CREATE TABLE IF NOT EXISTS nexus.verification_profile_steps (
 step_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 profile_id UUID NOT NULL REFERENCES nexus.verification_profiles(profile_id) ON DELETE CASCADE,
 position INTEGER NOT NULL,
 name TEXT NOT NULL,
 verifier_type TEXT NOT NULL,
 required BOOLEAN NOT NULL DEFAULT TRUE,
 timeout_seconds INTEGER NOT NULL DEFAULT 30,
 weight NUMERIC(8,3) NOT NULL DEFAULT 1,
 configuration JSONB NOT NULL DEFAULT '{}'::jsonb,
 expected JSONB NOT NULL DEFAULT '{}'::jsonb,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 UNIQUE(profile_id,position),
 CHECK(timeout_seconds BETWEEN 1 AND 600),
 CHECK(weight > 0)
);

CREATE TABLE IF NOT EXISTS nexus.verification_runs (
 run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 profile_id UUID REFERENCES nexus.verification_profiles(profile_id) ON DELETE SET NULL,
 profile_key TEXT NOT NULL DEFAULT '',
 change_id UUID REFERENCES nexus.change_requests(change_id) ON DELETE SET NULL,
 rollback_id UUID REFERENCES nexus.change_rollback_plans(rollback_id) ON DELETE SET NULL,
 target_type TEXT NOT NULL DEFAULT 'asset',
 target_id TEXT NOT NULL,
 asset_id TEXT,
 transport TEXT NOT NULL DEFAULT 'local',
 status TEXT NOT NULL DEFAULT 'queued',
 score NUMERIC(5,2) NOT NULL DEFAULT 0,
 result TEXT NOT NULL DEFAULT '',
 rollback_recommended BOOLEAN NOT NULL DEFAULT FALSE,
 parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
 context JSONB NOT NULL DEFAULT '{}'::jsonb,
 summary JSONB NOT NULL DEFAULT '{}'::jsonb,
 error_message TEXT NOT NULL DEFAULT '',
 requested_by TEXT NOT NULL DEFAULT 'operator',
 claimed_by TEXT NOT NULL DEFAULT '',
 lease_expires_at TIMESTAMPTZ,
 started_at TIMESTAMPTZ,
 completed_at TIMESTAMPTZ,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 CHECK(status IN ('queued','running','passed','failed','cancelled')),
 CHECK(score BETWEEN 0 AND 100)
);

CREATE TABLE IF NOT EXISTS nexus.verification_step_runs (
 step_run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 run_id UUID NOT NULL REFERENCES nexus.verification_runs(run_id) ON DELETE CASCADE,
 step_id UUID REFERENCES nexus.verification_profile_steps(step_id) ON DELETE SET NULL,
 position INTEGER NOT NULL,
 name TEXT NOT NULL,
 verifier_type TEXT NOT NULL,
 required BOOLEAN NOT NULL DEFAULT TRUE,
 weight NUMERIC(8,3) NOT NULL DEFAULT 1,
 status TEXT NOT NULL DEFAULT 'queued',
 expected JSONB NOT NULL DEFAULT '{}'::jsonb,
 actual JSONB NOT NULL DEFAULT '{}'::jsonb,
 result_data JSONB NOT NULL DEFAULT '{}'::jsonb,
 error_message TEXT NOT NULL DEFAULT '',
 duration_ms INTEGER,
 started_at TIMESTAMPTZ,
 completed_at TIMESTAMPTZ,
 CHECK(status IN ('queued','running','passed','failed','skipped'))
);

CREATE TABLE IF NOT EXISTS nexus.verification_evidence (
 evidence_id BIGSERIAL PRIMARY KEY,
 run_id UUID NOT NULL REFERENCES nexus.verification_runs(run_id) ON DELETE CASCADE,
 step_run_id UUID REFERENCES nexus.verification_step_runs(step_run_id) ON DELETE CASCADE,
 evidence_type TEXT NOT NULL,
 content JSONB NOT NULL DEFAULT '{}'::jsonb,
 stdout TEXT NOT NULL DEFAULT '',
 stderr TEXT NOT NULL DEFAULT '',
 exit_code INTEGER,
 timed_out BOOLEAN NOT NULL DEFAULT FALSE,
 collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nexus.verification_events (
 event_id BIGSERIAL PRIMARY KEY,
 run_id UUID NOT NULL REFERENCES nexus.verification_runs(run_id) ON DELETE CASCADE,
 event_type TEXT NOT NULL,
 actor TEXT NOT NULL DEFAULT 'nexus',
 message TEXT NOT NULL DEFAULT '',
 details JSONB NOT NULL DEFAULT '{}'::jsonb,
 occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_verification_runs_status ON nexus.verification_runs(status,created_at);
CREATE INDEX IF NOT EXISTS idx_verification_runs_change ON nexus.verification_runs(change_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_verification_step_runs_run ON nexus.verification_step_runs(run_id,position);
CREATE INDEX IF NOT EXISTS idx_verification_events_run ON nexus.verification_events(run_id,occurred_at);
CREATE INDEX IF NOT EXISTS idx_verification_evidence_run ON nexus.verification_evidence(run_id,collected_at);

INSERT INTO nexus.verification_profiles
(profile_key,name,description,target_type,rollback_on_failure,minimum_score,created_by)
VALUES ('nexus.local.identity','Nexus Local Identity Verification',
'Verifies allow-listed host.identity execution on the Nexus host.',
'asset',FALSE,100,'package-048')
ON CONFLICT(profile_key) DO NOTHING;

INSERT INTO nexus.verification_profile_steps
(profile_id,position,name,verifier_type,required,timeout_seconds,weight,configuration,expected)
SELECT profile_id,1,'Read host identity','capability',TRUE,15,1,
'{"capability":"host.identity"}'::jsonb,'{"exitCode":0}'::jsonb
FROM nexus.verification_profiles WHERE profile_key='nexus.local.identity'
ON CONFLICT(profile_id,position) DO NOTHING;

COMMIT;
