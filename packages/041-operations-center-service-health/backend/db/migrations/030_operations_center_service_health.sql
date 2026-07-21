BEGIN;
CREATE TABLE IF NOT EXISTS nexus.service_health_snapshots (
  snapshot_id TEXT PRIMARY KEY,
  service_id TEXT NOT NULL REFERENCES nexus.business_services(service_id) ON DELETE CASCADE,
  health_state TEXT NOT NULL,
  capacity_percent NUMERIC(6,2) NOT NULL DEFAULT 0,
  member_count INTEGER NOT NULL DEFAULT 0,
  active_member_count INTEGER NOT NULL DEFAULT 0,
  failed_required_count INTEGER NOT NULL DEFAULT 0,
  degraded_count INTEGER NOT NULL DEFAULT 0,
  evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
  observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_service_health_snapshots_service_time
  ON nexus.service_health_snapshots(service_id, observed_at DESC);

CREATE TABLE IF NOT EXISTS nexus.service_incidents (
  incident_id TEXT PRIMARY KEY,
  service_id TEXT NOT NULL REFERENCES nexus.business_services(service_id) ON DELETE CASCADE,
  severity TEXT NOT NULL CHECK (severity IN ('info','warning','degraded','critical')),
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','acknowledged','resolved','suppressed')),
  title TEXT NOT NULL,
  summary TEXT NOT NULL DEFAULT '',
  root_cause_asset_id TEXT REFERENCES nexus.assets(asset_id) ON DELETE SET NULL,
  affected_assets JSONB NOT NULL DEFAULT '[]'::jsonb,
  evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
  opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  resolved_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_service_incidents_open
  ON nexus.service_incidents(status, severity, opened_at DESC);

CREATE TABLE IF NOT EXISTS nexus.service_availability_rollups (
  service_id TEXT PRIMARY KEY REFERENCES nexus.business_services(service_id) ON DELETE CASCADE,
  current_state TEXT NOT NULL DEFAULT 'unknown',
  capacity_percent NUMERIC(6,2) NOT NULL DEFAULT 0,
  available_members INTEGER NOT NULL DEFAULT 0,
  total_members INTEGER NOT NULL DEFAULT 0,
  redundancy_state TEXT NOT NULL DEFAULT 'unknown',
  last_healthy_at TIMESTAMPTZ,
  last_changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMIT;
