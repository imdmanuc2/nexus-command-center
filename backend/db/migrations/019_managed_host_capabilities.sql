BEGIN;

CREATE TABLE IF NOT EXISTS nexus.managed_capability_executions (
    execution_id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES nexus.automation_runs(run_id) ON DELETE CASCADE,
    capability_id TEXT NOT NULL,
    target_asset_id TEXT NOT NULL,
    transport TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    approval_actor TEXT,
    host_key_verified BOOLEAN NOT NULL DEFAULT FALSE,
    outcome TEXT NOT NULL,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    structured_result JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_managed_capability_execution_run ON nexus.managed_capability_executions(run_id, created_at DESC);

INSERT INTO nexus.automation_actions(
 action_id,name,description,action_type,entity_type,risk_level,
 requires_approval,supports_dry_run,timeout_seconds,retry_limit,
 command_template,metadata
) VALUES
('host.identity','Read Host Identity','Read kernel and operating-system identity using a typed capability.','managed-capability','server','low',FALSE,TRUE,15,1,'{"capability":"host.identity"}'::jsonb,'{"typed":true,"readOnly":true}'::jsonb),
('host.disk-usage','Read Host Disk Usage','Read bounded filesystem capacity details.','managed-capability','server','low',FALSE,TRUE,20,1,'{"capability":"host.disk-usage"}'::jsonb,'{"typed":true,"readOnly":true}'::jsonb),
('host.memory','Read Host Memory','Read host memory utilization.','managed-capability','server','low',FALSE,TRUE,15,1,'{"capability":"host.memory"}'::jsonb,'{"typed":true,"readOnly":true}'::jsonb),
('service.status','Read Service Status','Read an allow-listed systemd service state.','managed-capability','server','low',FALSE,TRUE,20,1,'{"capability":"service.status"}'::jsonb,'{"typed":true,"readOnly":true}'::jsonb),
('service.restart','Restart Service','Restart an allow-listed systemd service and verify it returns active.','managed-capability','server','high',TRUE,TRUE,90,1,'{"capability":"service.restart"}'::jsonb,'{"typed":true,"postActionVerification":true}'::jsonb),
('service.journal','Collect Service Journal','Collect a bounded, redacted systemd journal excerpt.','managed-capability','server','low',FALSE,TRUE,30,1,'{"capability":"service.journal"}'::jsonb,'{"typed":true,"readOnly":true,"redacted":true}'::jsonb)
ON CONFLICT(action_id) DO UPDATE SET
 name=EXCLUDED.name,description=EXCLUDED.description,action_type=EXCLUDED.action_type,
 entity_type=EXCLUDED.entity_type,risk_level=EXCLUDED.risk_level,
 requires_approval=EXCLUDED.requires_approval,supports_dry_run=EXCLUDED.supports_dry_run,
 timeout_seconds=EXCLUDED.timeout_seconds,retry_limit=EXCLUDED.retry_limit,
 command_template=EXCLUDED.command_template,metadata=EXCLUDED.metadata,enabled=TRUE,updated_at=NOW();

INSERT INTO public.schema_migrations(version,description)
VALUES('019','Typed managed host capabilities and secure transport foundation')
ON CONFLICT(version) DO NOTHING;
COMMIT;
