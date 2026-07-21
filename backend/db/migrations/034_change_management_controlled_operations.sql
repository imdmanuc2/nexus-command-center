BEGIN;

CREATE TABLE IF NOT EXISTS nexus.change_templates (
  template_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  capability TEXT NOT NULL,
  target_type TEXT NOT NULL DEFAULT 'asset',
  risk_level TEXT NOT NULL DEFAULT 'medium'
    CHECK (risk_level IN ('low','medium','high','critical')),
  approval_required BOOLEAN NOT NULL DEFAULT TRUE,
  maintenance_required BOOLEAN NOT NULL DEFAULT FALSE,
  rollback_capability TEXT NOT NULL DEFAULT '',
  timeout_seconds INTEGER NOT NULL DEFAULT 300 CHECK (timeout_seconds BETWEEN 1 AND 86400),
  default_parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nexus.change_requests (
  change_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  change_number TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  template_id TEXT REFERENCES nexus.change_templates(template_id) ON DELETE SET NULL,
  capability TEXT NOT NULL,
  rollback_capability TEXT NOT NULL DEFAULT '',
  target_type TEXT NOT NULL DEFAULT 'asset',
  target_id TEXT NOT NULL,
  asset_id TEXT REFERENCES nexus.assets(asset_id) ON DELETE SET NULL,
  service_id TEXT REFERENCES nexus.business_services(service_id) ON DELETE SET NULL,
  maintenance_window_id UUID REFERENCES nexus.maintenance_windows(window_id) ON DELETE SET NULL,
  status TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN (
      'draft','pending-approval','approved','scheduled','executing',
      'completed','failed','rollback-pending','rolling-back',
      'rolled-back','cancelled'
    )),
  risk_level TEXT NOT NULL DEFAULT 'medium'
    CHECK (risk_level IN ('low','medium','high','critical')),
  approval_required BOOLEAN NOT NULL DEFAULT TRUE,
  maintenance_required BOOLEAN NOT NULL DEFAULT FALSE,
  requested_by TEXT NOT NULL DEFAULT 'operator',
  approved_by TEXT NOT NULL DEFAULT '',
  approved_at TIMESTAMPTZ,
  scheduled_for TIMESTAMPTZ,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  operation_id TEXT,
  rollback_operation_id TEXT,
  parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
  impact_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
  maintenance_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
  execution_result JSONB NOT NULL DEFAULT '{}'::jsonb,
  failure_reason TEXT NOT NULL DEFAULT '',
  correlation_id TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE SEQUENCE IF NOT EXISTS nexus.change_number_seq START 1000;

CREATE TABLE IF NOT EXISTS nexus.change_steps (
  step_id BIGSERIAL PRIMARY KEY,
  change_id UUID NOT NULL REFERENCES nexus.change_requests(change_id) ON DELETE CASCADE,
  position INTEGER NOT NULL,
  name TEXT NOT NULL,
  capability TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','running','succeeded','failed','skipped','rolled-back')),
  output JSONB NOT NULL DEFAULT '{}'::jsonb,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  UNIQUE(change_id, position)
);

CREATE TABLE IF NOT EXISTS nexus.change_approvals (
  approval_id BIGSERIAL PRIMARY KEY,
  change_id UUID NOT NULL REFERENCES nexus.change_requests(change_id) ON DELETE CASCADE,
  decision TEXT NOT NULL CHECK (decision IN ('approved','rejected')),
  actor TEXT NOT NULL,
  reason TEXT NOT NULL DEFAULT '',
  decided_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nexus.change_execution_log (
  log_id BIGSERIAL PRIMARY KEY,
  change_id UUID NOT NULL REFERENCES nexus.change_requests(change_id) ON DELETE CASCADE,
  event_type TEXT NOT NULL,
  actor TEXT NOT NULL DEFAULT 'nexus',
  message TEXT NOT NULL DEFAULT '',
  details JSONB NOT NULL DEFAULT '{}'::jsonb,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_change_requests_status
  ON nexus.change_requests(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_change_requests_target
  ON nexus.change_requests(target_type, target_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_change_execution_log_change
  ON nexus.change_execution_log(change_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_change_approvals_change
  ON nexus.change_approvals(change_id, decided_at DESC);

INSERT INTO nexus.change_templates
(template_id,name,description,capability,target_type,risk_level,approval_required,
 maintenance_required,rollback_capability,timeout_seconds,default_parameters)
VALUES
('service-restart','Restart Managed Service',
 'Restart an allow-listed systemd service and verify recovery.',
 'service.restart','asset','high',TRUE,TRUE,'service.restart',300,
 '{"serviceName":""}'::jsonb),
('service-diagnostics','Run Service Diagnostics',
 'Collect status and bounded diagnostic output without changing the target.',
 'service.status','asset','low',FALSE,FALSE,'',120,
 '{"serviceName":""}'::jsonb),
('host-identity','Read Managed Host Identity',
 'Read operating-system and kernel identity through the managed capability transport.',
 'host.identity','asset','low',FALSE,FALSE,'',60,
 '{}'::jsonb),
('asset-rescan','Rescan Managed Asset',
 'Request a targeted infrastructure discovery scan.',
 'discovery.asset.rescan','asset','medium',FALSE,FALSE,'',300,
 '{}'::jsonb)
ON CONFLICT (template_id) DO UPDATE SET
  name=EXCLUDED.name,
  description=EXCLUDED.description,
  capability=EXCLUDED.capability,
  target_type=EXCLUDED.target_type,
  risk_level=EXCLUDED.risk_level,
  approval_required=EXCLUDED.approval_required,
  maintenance_required=EXCLUDED.maintenance_required,
  rollback_capability=EXCLUDED.rollback_capability,
  timeout_seconds=EXCLUDED.timeout_seconds,
  default_parameters=EXCLUDED.default_parameters,
  active=TRUE,
  updated_at=NOW();

COMMIT;
