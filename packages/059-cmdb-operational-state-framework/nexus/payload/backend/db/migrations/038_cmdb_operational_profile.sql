BEGIN;

ALTER TABLE nexus.assets
  ADD COLUMN IF NOT EXISTS mission TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS operational_role TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS management_model TEXT NOT NULL DEFAULT 'nexus-managed',
  ADD COLUMN IF NOT EXISTS lifecycle_stage TEXT NOT NULL DEFAULT 'production',
  ADD COLUMN IF NOT EXISTS desired_operational_mode TEXT NOT NULL DEFAULT 'automatic',
  ADD COLUMN IF NOT EXISTS observed_operational_mode TEXT NOT NULL DEFAULT 'unknown',
  ADD COLUMN IF NOT EXISTS health_state TEXT NOT NULL DEFAULT 'unknown',
  ADD COLUMN IF NOT EXISTS connectivity_state TEXT NOT NULL DEFAULT 'unknown';

DO $$ BEGIN
  ALTER TABLE nexus.assets ADD CONSTRAINT assets_management_model_check
    CHECK (management_model IN ('nexus-managed','customer-managed','observed'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  ALTER TABLE nexus.assets ADD CONSTRAINT assets_lifecycle_stage_check
    CHECK (lifecycle_stage IN ('discovered','provisioning','commissioning','production','maintenance','decommissioning','retired'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  ALTER TABLE nexus.assets ADD CONSTRAINT assets_health_state_check
    CHECK (health_state IN ('healthy','warning','critical','unknown'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  ALTER TABLE nexus.assets ADD CONSTRAINT assets_connectivity_state_check
    CHECK (connectivity_state IN ('connected','disconnected','intermittent','unknown'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS nexus.asset_operational_profile_history (
  history_id BIGSERIAL PRIMARY KEY,
  asset_id TEXT NOT NULL REFERENCES nexus.assets(asset_id) ON DELETE CASCADE,
  previous_profile JSONB NOT NULL DEFAULT '{}'::JSONB,
  new_profile JSONB NOT NULL DEFAULT '{}'::JSONB,
  reason TEXT NOT NULL DEFAULT '',
  changed_by TEXT NOT NULL DEFAULT 'nexus',
  source TEXT NOT NULL DEFAULT 'cmdb-operational-profile',
  correlation_id TEXT NOT NULL DEFAULT '',
  changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_asset_operational_profile_history
  ON nexus.asset_operational_profile_history(asset_id, changed_at DESC);

INSERT INTO schema_migrations(version, description)
VALUES ('038', 'CMDB operational profile and object state framework')
ON CONFLICT (version) DO NOTHING;

COMMIT;
