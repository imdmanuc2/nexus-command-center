BEGIN;
CREATE TABLE IF NOT EXISTS nexus.business_services (
  service_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  service_type TEXT NOT NULL DEFAULT 'infrastructure',
  description TEXT NOT NULL DEFAULT '',
  owner TEXT NOT NULL DEFAULT '',
  criticality TEXT NOT NULL DEFAULT 'normal' CHECK (criticality IN ('low','normal','high','critical')),
  operational_state TEXT NOT NULL DEFAULT 'active',
  desired_state TEXT NOT NULL DEFAULT 'available',
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL DEFAULT 'nexus',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS nexus.business_service_members (
  membership_id TEXT PRIMARY KEY,
  service_id TEXT NOT NULL REFERENCES nexus.business_services(service_id) ON DELETE CASCADE,
  asset_id TEXT NOT NULL REFERENCES nexus.assets(asset_id) ON DELETE CASCADE,
  role TEXT NOT NULL DEFAULT 'component',
  required BOOLEAN NOT NULL DEFAULT TRUE,
  weight NUMERIC(6,2) NOT NULL DEFAULT 1,
  source TEXT NOT NULL DEFAULT 'cmdb',
  confidence NUMERIC(5,2) NOT NULL DEFAULT 100,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(service_id, asset_id, role)
);
CREATE INDEX IF NOT EXISTS idx_business_service_members_service ON nexus.business_service_members(service_id);
CREATE INDEX IF NOT EXISTS idx_business_service_members_asset ON nexus.business_service_members(asset_id);
CREATE TABLE IF NOT EXISTS nexus.business_service_dependencies (
  dependency_id TEXT PRIMARY KEY,
  service_id TEXT NOT NULL REFERENCES nexus.business_services(service_id) ON DELETE CASCADE,
  depends_on_service_id TEXT NOT NULL REFERENCES nexus.business_services(service_id) ON DELETE CASCADE,
  required BOOLEAN NOT NULL DEFAULT TRUE,
  confidence NUMERIC(5,2) NOT NULL DEFAULT 100,
  reason TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(service_id, depends_on_service_id),
  CHECK(service_id <> depends_on_service_id)
);
CREATE TABLE IF NOT EXISTS nexus.business_service_history (
  history_id TEXT PRIMARY KEY,
  service_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  before_state JSONB NOT NULL DEFAULT '{}'::jsonb,
  after_state JSONB NOT NULL DEFAULT '{}'::jsonb,
  reason TEXT NOT NULL DEFAULT '',
  changed_by TEXT NOT NULL DEFAULT 'nexus',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_business_service_history_service ON nexus.business_service_history(service_id, created_at DESC);

INSERT INTO nexus.business_services(service_id,name,service_type,description,criticality,metadata) VALUES
('svc-bitcoin-mining','Bitcoin Mining Service','mining','End-to-end Bitcoin mining capability including compute, pool, RPC, node, host, network, and power dependencies.','critical','{"workloadCategories":["mining"],"coin":"BTC"}'::jsonb),
('svc-ai-compute','AI Compute Service','ai-compute','GPU and CPU resources assigned to AI inference or training workloads.','high','{"workloadCategories":["ai-inference","ai-training"]}'::jsonb),
('svc-rentable-compute','Rentable Compute Capacity','compute-rental','GPU and CPU capacity offered through external rental providers.','high','{"workloadCategories":["gpu-rental","cpu-rental"]}'::jsonb)
ON CONFLICT(service_id) DO UPDATE SET name=EXCLUDED.name,description=EXCLUDED.description,criticality=EXCLUDED.criticality,metadata=EXCLUDED.metadata,updated_at=NOW();

-- Automatically associate current workload assets with the matching service templates.
INSERT INTO nexus.business_service_members(membership_id,service_id,asset_id,role,required,source,confidence)
SELECT 'bsm-' || md5(s.service_id || ':' || w.asset_id), s.service_id, w.asset_id, 'workload-host', TRUE, 'workload-assignment', 95
FROM nexus.business_services s
JOIN nexus.workload_assignments w ON (s.metadata->'workloadCategories') ? w.workload_category
WHERE w.status IN ('assigned','active','running')
ON CONFLICT(service_id,asset_id,role) DO NOTHING;
COMMIT;
