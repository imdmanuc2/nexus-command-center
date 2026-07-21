BEGIN;
CREATE TABLE IF NOT EXISTS nexus.service_impact_snapshots (
  snapshot_id text PRIMARY KEY,
  service_id text NOT NULL REFERENCES nexus.business_services(service_id) ON DELETE CASCADE,
  health_state text NOT NULL,
  root_cause_asset_id text,
  affected_asset_count integer NOT NULL DEFAULT 0,
  affected_service_count integer NOT NULL DEFAULT 0,
  capacity_percent numeric(6,2) NOT NULL DEFAULT 0,
  analysis jsonb NOT NULL DEFAULT '{}'::jsonb,
  observed_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_service_impact_snapshots_service_time ON nexus.service_impact_snapshots(service_id, observed_at DESC);
CREATE TABLE IF NOT EXISTS nexus.service_dependency_rules (
  rule_id text PRIMARY KEY,
  service_id text NOT NULL REFERENCES nexus.business_services(service_id) ON DELETE CASCADE,
  relationship_type text NOT NULL,
  direction text NOT NULL DEFAULT 'both',
  required boolean NOT NULL DEFAULT false,
  max_depth integer NOT NULL DEFAULT 3,
  active boolean NOT NULL DEFAULT true,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(service_id, relationship_type, direction)
);
INSERT INTO nexus.service_dependency_rules(rule_id,service_id,relationship_type,direction,required,max_depth,metadata)
VALUES
('sdr-bitcoin-depends-on','svc-bitcoin-mining','depends-on','both',true,4,'{"source":"nexus-default"}'),
('sdr-bitcoin-connects-to','svc-bitcoin-mining','connects-to','both',false,3,'{"source":"nexus-default"}'),
('sdr-bitcoin-runs-on','svc-bitcoin-mining','runs-on','both',true,3,'{"source":"nexus-default"}'),
('sdr-bitcoin-mines-on','svc-bitcoin-mining','mines-on','both',true,3,'{"source":"nexus-default"}')
ON CONFLICT DO NOTHING;
COMMIT;
