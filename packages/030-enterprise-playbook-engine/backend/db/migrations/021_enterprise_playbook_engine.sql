BEGIN;

CREATE SCHEMA IF NOT EXISTS nexus;

CREATE TABLE IF NOT EXISTS nexus.playbooks (
  playbook_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL DEFAULT 'operations',
  risk_level TEXT NOT NULL DEFAULT 'low',
  current_version TEXT NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  source_path TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Reconcile older/partial playbook tables. CREATE TABLE IF NOT EXISTS does not
-- add columns to a table that already exists, so every Package 030 column is
-- added explicitly and idempotently.
ALTER TABLE nexus.playbooks ADD COLUMN IF NOT EXISTS playbook_id TEXT;
ALTER TABLE nexus.playbooks ADD COLUMN IF NOT EXISTS name TEXT;
ALTER TABLE nexus.playbooks ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT '';
ALTER TABLE nexus.playbooks ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'operations';
ALTER TABLE nexus.playbooks ADD COLUMN IF NOT EXISTS risk_level TEXT NOT NULL DEFAULT 'low';
ALTER TABLE nexus.playbooks ADD COLUMN IF NOT EXISTS current_version TEXT;
ALTER TABLE nexus.playbooks ADD COLUMN IF NOT EXISTS enabled BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE nexus.playbooks ADD COLUMN IF NOT EXISTS source_path TEXT;
ALTER TABLE nexus.playbooks ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE nexus.playbooks ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
CREATE UNIQUE INDEX IF NOT EXISTS uq_playbooks_playbook_id ON nexus.playbooks(playbook_id);

CREATE TABLE IF NOT EXISTS nexus.playbook_versions (
  playbook_id TEXT NOT NULL,
  version TEXT NOT NULL,
  definition JSONB NOT NULL,
  definition_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE nexus.playbook_versions ADD COLUMN IF NOT EXISTS playbook_id TEXT;
ALTER TABLE nexus.playbook_versions ADD COLUMN IF NOT EXISTS version TEXT;
ALTER TABLE nexus.playbook_versions ADD COLUMN IF NOT EXISTS definition JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE nexus.playbook_versions ADD COLUMN IF NOT EXISTS definition_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE nexus.playbook_versions ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
CREATE UNIQUE INDEX IF NOT EXISTS uq_playbook_versions_id_version ON nexus.playbook_versions(playbook_id, version);

CREATE TABLE IF NOT EXISTS nexus.playbook_runs (
  run_id TEXT PRIMARY KEY,
  playbook_id TEXT NOT NULL,
  playbook_version TEXT NOT NULL,
  operation_session_id TEXT,
  target_asset_id TEXT,
  target_type TEXT,
  status TEXT NOT NULL,
  requested_by TEXT NOT NULL DEFAULT 'nexus-user',
  variables JSONB NOT NULL DEFAULT '{}'::jsonb,
  result JSONB NOT NULL DEFAULT '{}'::jsonb,
  error_message TEXT,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE nexus.playbook_runs ADD COLUMN IF NOT EXISTS run_id TEXT;
ALTER TABLE nexus.playbook_runs ADD COLUMN IF NOT EXISTS playbook_id TEXT;
ALTER TABLE nexus.playbook_runs ADD COLUMN IF NOT EXISTS playbook_version TEXT;
ALTER TABLE nexus.playbook_runs ADD COLUMN IF NOT EXISTS operation_session_id TEXT;
ALTER TABLE nexus.playbook_runs ADD COLUMN IF NOT EXISTS target_asset_id TEXT;
ALTER TABLE nexus.playbook_runs ADD COLUMN IF NOT EXISTS target_type TEXT;
ALTER TABLE nexus.playbook_runs ADD COLUMN IF NOT EXISTS status TEXT;
ALTER TABLE nexus.playbook_runs ADD COLUMN IF NOT EXISTS requested_by TEXT NOT NULL DEFAULT 'nexus-user';
ALTER TABLE nexus.playbook_runs ADD COLUMN IF NOT EXISTS variables JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE nexus.playbook_runs ADD COLUMN IF NOT EXISTS result JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE nexus.playbook_runs ADD COLUMN IF NOT EXISTS error_message TEXT;
ALTER TABLE nexus.playbook_runs ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ;
ALTER TABLE nexus.playbook_runs ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;
ALTER TABLE nexus.playbook_runs ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE nexus.playbook_runs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
CREATE UNIQUE INDEX IF NOT EXISTS uq_playbook_runs_run_id ON nexus.playbook_runs(run_id);

CREATE TABLE IF NOT EXISTS nexus.playbook_steps (
  step_run_id BIGSERIAL PRIMARY KEY,
  run_id TEXT NOT NULL,
  step_id TEXT NOT NULL,
  position INTEGER NOT NULL,
  capability TEXT NOT NULL,
  status TEXT NOT NULL,
  parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
  result JSONB NOT NULL DEFAULT '{}'::jsonb,
  error_message TEXT,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ
);
ALTER TABLE nexus.playbook_steps ADD COLUMN IF NOT EXISTS step_run_id BIGSERIAL;
ALTER TABLE nexus.playbook_steps ADD COLUMN IF NOT EXISTS run_id TEXT;
ALTER TABLE nexus.playbook_steps ADD COLUMN IF NOT EXISTS step_id TEXT;
ALTER TABLE nexus.playbook_steps ADD COLUMN IF NOT EXISTS position INTEGER;
ALTER TABLE nexus.playbook_steps ADD COLUMN IF NOT EXISTS capability TEXT;
ALTER TABLE nexus.playbook_steps ADD COLUMN IF NOT EXISTS status TEXT;
ALTER TABLE nexus.playbook_steps ADD COLUMN IF NOT EXISTS parameters JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE nexus.playbook_steps ADD COLUMN IF NOT EXISTS result JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE nexus.playbook_steps ADD COLUMN IF NOT EXISTS error_message TEXT;
ALTER TABLE nexus.playbook_steps ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ;
ALTER TABLE nexus.playbook_steps ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;
CREATE UNIQUE INDEX IF NOT EXISTS uq_playbook_steps_step_run_id ON nexus.playbook_steps(step_run_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_playbook_steps_run_step ON nexus.playbook_steps(run_id, step_id);

CREATE INDEX IF NOT EXISTS idx_playbook_runs_created ON nexus.playbook_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_playbook_steps_run_position ON nexus.playbook_steps(run_id, position);

COMMIT;
