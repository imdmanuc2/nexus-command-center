BEGIN;
CREATE SCHEMA IF NOT EXISTS nexus;
CREATE TABLE IF NOT EXISTS nexus.automation_control_audit (
    audit_id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES nexus.automation_runs(run_id) ON DELETE CASCADE,
    action_id TEXT NOT NULL,
    control_action TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'operator',
    previous_status TEXT NOT NULL DEFAULT '',
    new_status TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL DEFAULT '',
    details JSONB NOT NULL DEFAULT '{}'::JSONB,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_automation_control_audit_run
ON nexus.automation_control_audit(run_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_automation_control_audit_action
ON nexus.automation_control_audit(action_id, occurred_at DESC);
INSERT INTO schema_migrations(version, description)
VALUES ('017','Operations Center action execution, approval controls, and audit trail')
ON CONFLICT(version) DO NOTHING;
COMMIT;
