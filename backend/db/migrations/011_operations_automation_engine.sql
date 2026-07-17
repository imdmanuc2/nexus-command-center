BEGIN;
CREATE SCHEMA IF NOT EXISTS nexus;
CREATE TABLE IF NOT EXISTS nexus.automation_actions (
 action_id TEXT PRIMARY KEY,
 name TEXT NOT NULL,
 description TEXT NOT NULL DEFAULT '',
 action_type TEXT NOT NULL,
 entity_type TEXT NOT NULL DEFAULT '*',
 risk_level TEXT NOT NULL DEFAULT 'low',
 requires_approval BOOLEAN NOT NULL DEFAULT TRUE,
 supports_dry_run BOOLEAN NOT NULL DEFAULT TRUE,
 timeout_seconds INTEGER NOT NULL DEFAULT 60,
 retry_limit INTEGER NOT NULL DEFAULT 0,
 command_template JSONB NOT NULL DEFAULT '{}'::JSONB,
 enabled BOOLEAN NOT NULL DEFAULT TRUE,
 metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS nexus.automation_runs (
 run_id TEXT PRIMARY KEY,
 action_id TEXT NOT NULL REFERENCES nexus.automation_actions(action_id),
 recommendation_id TEXT,
 entity_type TEXT NOT NULL,
 entity_id TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending-approval',
 requested_by TEXT NOT NULL DEFAULT 'operator',
 approved_by TEXT NOT NULL DEFAULT '',
 dry_run BOOLEAN NOT NULL DEFAULT TRUE,
 attempt_count INTEGER NOT NULL DEFAULT 0,
 input_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
 execution_plan JSONB NOT NULL DEFAULT '{}'::JSONB,
 result_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
 error_message TEXT NOT NULL DEFAULT '',
 requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 approved_at TIMESTAMPTZ,
 started_at TIMESTAMPTZ,
 completed_at TIMESTAMPTZ,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_automation_runs_status ON nexus.automation_runs(status, requested_at);
CREATE INDEX IF NOT EXISTS idx_automation_runs_entity ON nexus.automation_runs(entity_type, entity_id, requested_at DESC);
CREATE TABLE IF NOT EXISTS nexus.automation_engine_state (
 engine_name TEXT PRIMARY KEY,
 last_started_at TIMESTAMPTZ,
 last_completed_at TIMESTAMPTZ,
 last_status TEXT NOT NULL DEFAULT 'never-run',
 last_error TEXT NOT NULL DEFAULT '',
 pending_runs INTEGER NOT NULL DEFAULT 0,
 processed_runs INTEGER NOT NULL DEFAULT 0,
 failed_runs INTEGER NOT NULL DEFAULT 0,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
INSERT INTO nexus.automation_actions(action_id,name,description,action_type,entity_type,risk_level,requires_approval,supports_dry_run,timeout_seconds,retry_limit,command_template,metadata)
VALUES
('refresh-platform-sync','Refresh Platform State','Run the Nexus Platform synchronization pipeline immediately.','internal-job','platform','low',FALSE,TRUE,120,1,'{"job":"backend.jobs.platform_sync_job"}'::JSONB,'{"safe":true}'::JSONB),
('refresh-resource-sync','Refresh Resource Persistence','Refresh blockchain-node and MiningCore persistence.','internal-job','*','low',FALSE,TRUE,60,1,'{"job":"backend.jobs.platform_resource_sync"}'::JSONB,'{"safe":true}'::JSONB),
('restart-miningcore-service','Restart MiningCore Service','Restart a managed MiningCore service through an approved executor.','service-restart','miningcore-instance','high',TRUE,TRUE,120,1,'{"executor":"managed-host","operation":"restart-service","service":"miningcore"}'::JSONB,'{"requiresManagedHost":true}'::JSONB),
('rescan-worker','Rescan Worker','Trigger worker discovery and inventory reconciliation.','discovery-scan','worker','low',FALSE,TRUE,120,1,'{"executor":"nexus","operation":"rescan-worker"}'::JSONB,'{"safe":true}'::JSONB),
('test-blockchain-rpc','Test Blockchain RPC','Run a non-destructive blockchain RPC connectivity check.','rpc-test','blockchain-node','low',FALSE,TRUE,30,1,'{"executor":"nexus","operation":"test-rpc"}'::JSONB,'{"safe":true}'::JSONB)
ON CONFLICT(action_id) DO NOTHING;
INSERT INTO public.schema_migrations(version,description) VALUES('011','Guarded operations automation engine') ON CONFLICT(version) DO NOTHING;
COMMIT;
