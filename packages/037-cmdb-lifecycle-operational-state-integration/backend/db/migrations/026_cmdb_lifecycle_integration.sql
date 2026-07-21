BEGIN;
ALTER TABLE nexus.assets
  ADD COLUMN IF NOT EXISTS desired_operational_state TEXT NOT NULL DEFAULT 'online',
  ADD COLUMN IF NOT EXISTS commissioned_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS in_service_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS decommissioned_at TIMESTAMPTZ;
DO $$ BEGIN
  ALTER TABLE nexus.assets ADD CONSTRAINT assets_desired_operational_state_check
    CHECK (desired_operational_state IN ('online','offline'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
CREATE TABLE IF NOT EXISTS nexus.asset_lifecycle_history (
  history_id BIGSERIAL PRIMARY KEY,
  asset_id TEXT NOT NULL REFERENCES nexus.assets(asset_id) ON DELETE CASCADE,
  event_type TEXT NOT NULL,
  field_name TEXT NOT NULL,
  previous_value TEXT,
  new_value TEXT,
  reason TEXT NOT NULL DEFAULT '',
  changed_by TEXT NOT NULL DEFAULT 'nexus',
  source TEXT NOT NULL DEFAULT 'cmdb',
  correlation_id TEXT NOT NULL DEFAULT '',
  metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
  changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_asset_lifecycle_history_asset_time ON nexus.asset_lifecycle_history(asset_id, changed_at DESC);
INSERT INTO schema_migrations(version,description) VALUES ('026','CMDB lifecycle and operational state integration') ON CONFLICT(version) DO NOTHING;
COMMIT;
