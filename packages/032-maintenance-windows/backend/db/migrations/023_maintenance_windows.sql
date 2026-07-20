BEGIN;

CREATE TABLE IF NOT EXISTS nexus.maintenance_windows (
  window_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'scheduled'
    CHECK (status IN ('scheduled','active','completed','cancelled')),
  starts_at TIMESTAMPTZ NOT NULL,
  ends_at TIMESTAMPTZ NOT NULL,
  created_by TEXT NOT NULL DEFAULT 'nexus',
  reason TEXT NOT NULL DEFAULT '',
  suppress_alerts BOOLEAN NOT NULL DEFAULT TRUE,
  suppress_recommendations BOOLEAN NOT NULL DEFAULT TRUE,
  metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  cancelled_at TIMESTAMPTZ,
  CHECK (ends_at > starts_at)
);

CREATE TABLE IF NOT EXISTS nexus.maintenance_targets (
  target_id BIGSERIAL PRIMARY KEY,
  window_id UUID NOT NULL REFERENCES nexus.maintenance_windows(window_id) ON DELETE CASCADE,
  target_type TEXT NOT NULL
    CHECK (target_type IN ('asset','asset_type','site','rack','pool','cluster','tag')),
  target_value TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(window_id, target_type, target_value)
);

CREATE INDEX IF NOT EXISTS idx_maintenance_windows_time
  ON nexus.maintenance_windows(starts_at, ends_at);
CREATE INDEX IF NOT EXISTS idx_maintenance_windows_status
  ON nexus.maintenance_windows(status);
CREATE INDEX IF NOT EXISTS idx_maintenance_targets_lookup
  ON nexus.maintenance_targets(target_type, target_value);

COMMIT;
