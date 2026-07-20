BEGIN;
CREATE SCHEMA IF NOT EXISTS nexus;
CREATE TABLE IF NOT EXISTS nexus.execution_policies (
  policy_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  operation_class TEXT NOT NULL,
  decision TEXT NOT NULL CHECK (decision IN ('allow','deny','confirmation_required')),
  requires_confirmation BOOLEAN NOT NULL DEFAULT FALSE,
  priority INTEGER NOT NULL DEFAULT 100,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE nexus.execution_policies ADD COLUMN IF NOT EXISTS policy_id TEXT;
ALTER TABLE nexus.execution_policies ADD COLUMN IF NOT EXISTS name TEXT;
ALTER TABLE nexus.execution_policies ADD COLUMN IF NOT EXISTS operation_class TEXT;
ALTER TABLE nexus.execution_policies ADD COLUMN IF NOT EXISTS decision TEXT;
ALTER TABLE nexus.execution_policies ADD COLUMN IF NOT EXISTS requires_confirmation BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE nexus.execution_policies ADD COLUMN IF NOT EXISTS priority INTEGER NOT NULL DEFAULT 100;
ALTER TABLE nexus.execution_policies ADD COLUMN IF NOT EXISTS enabled BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE nexus.execution_policies ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE nexus.execution_policies ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
CREATE UNIQUE INDEX IF NOT EXISTS uq_execution_policies_policy_id ON nexus.execution_policies(policy_id);

CREATE TABLE IF NOT EXISTS nexus.policy_decisions (
  decision_id BIGSERIAL PRIMARY KEY,
  operation TEXT NOT NULL,
  decision TEXT NOT NULL,
  policy_id TEXT NOT NULL,
  requested_by TEXT NOT NULL DEFAULT 'nexus-user',
  target_asset_id TEXT,
  playbook_id TEXT,
  confirmed BOOLEAN NOT NULL DEFAULT FALSE,
  reason TEXT NOT NULL DEFAULT '',
  context JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE nexus.policy_decisions ADD COLUMN IF NOT EXISTS decision_id BIGSERIAL;
ALTER TABLE nexus.policy_decisions ADD COLUMN IF NOT EXISTS operation TEXT;
ALTER TABLE nexus.policy_decisions ADD COLUMN IF NOT EXISTS decision TEXT;
ALTER TABLE nexus.policy_decisions ADD COLUMN IF NOT EXISTS policy_id TEXT;
ALTER TABLE nexus.policy_decisions ADD COLUMN IF NOT EXISTS requested_by TEXT NOT NULL DEFAULT 'nexus-user';
ALTER TABLE nexus.policy_decisions ADD COLUMN IF NOT EXISTS target_asset_id TEXT;
ALTER TABLE nexus.policy_decisions ADD COLUMN IF NOT EXISTS playbook_id TEXT;
ALTER TABLE nexus.policy_decisions ADD COLUMN IF NOT EXISTS confirmed BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE nexus.policy_decisions ADD COLUMN IF NOT EXISTS reason TEXT NOT NULL DEFAULT '';
ALTER TABLE nexus.policy_decisions ADD COLUMN IF NOT EXISTS context JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE nexus.policy_decisions ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
CREATE UNIQUE INDEX IF NOT EXISTS uq_policy_decisions_id ON nexus.policy_decisions(decision_id);
CREATE INDEX IF NOT EXISTS idx_policy_decisions_created ON nexus.policy_decisions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_policy_decisions_operation ON nexus.policy_decisions(operation, created_at DESC);
COMMIT;
