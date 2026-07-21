BEGIN;

ALTER TABLE nexus.assets
  ADD COLUMN IF NOT EXISTS operational_state TEXT NOT NULL DEFAULT 'active',
  ADD COLUMN IF NOT EXISTS operational_state_reason TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS operational_state_changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS operational_state_changed_by TEXT NOT NULL DEFAULT 'nexus';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'assets_operational_state_check'
      AND conrelid = 'nexus.assets'::regclass
  ) THEN
    ALTER TABLE nexus.assets ADD CONSTRAINT assets_operational_state_check
      CHECK (operational_state IN (
        'active','maintenance','disabled','provisioning','decommissioning','retired'
      ));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_assets_operational_state
  ON nexus.assets(operational_state);

CREATE TABLE IF NOT EXISTS nexus.asset_operational_state_history (
  history_id BIGSERIAL PRIMARY KEY,
  asset_id TEXT NOT NULL REFERENCES nexus.assets(asset_id) ON DELETE CASCADE,
  previous_state TEXT,
  new_state TEXT NOT NULL,
  reason TEXT NOT NULL DEFAULT '',
  changed_by TEXT NOT NULL DEFAULT 'nexus',
  source TEXT NOT NULL DEFAULT 'operational-state',
  correlation_id TEXT NOT NULL DEFAULT '',
  metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
  changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CHECK (new_state IN (
    'active','maintenance','disabled','provisioning','decommissioning','retired'
  ))
);
CREATE INDEX IF NOT EXISTS idx_asset_state_history_asset
  ON nexus.asset_operational_state_history(asset_id, changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_asset_state_history_state
  ON nexus.asset_operational_state_history(new_state, changed_at DESC);

INSERT INTO schema_migrations(version, description)
VALUES ('025', 'Asset operational state and immutable state history')
ON CONFLICT (version) DO NOTHING;

COMMIT;
