BEGIN;
ALTER TABLE nexus.relationships
  ADD COLUMN IF NOT EXISTS criticality TEXT NOT NULL DEFAULT 'normal',
  ADD COLUMN IF NOT EXISTS redundancy_group TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS verification_status TEXT NOT NULL DEFAULT 'unverified',
  ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS created_by TEXT NOT NULL DEFAULT 'nexus',
  ADD COLUMN IF NOT EXISTS updated_by TEXT NOT NULL DEFAULT 'nexus';

CREATE TABLE IF NOT EXISTS nexus.relationship_type_catalog (
  relationship_type TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  source_entity_types JSONB NOT NULL DEFAULT '[]'::jsonb,
  target_entity_types JSONB NOT NULL DEFAULT '[]'::jsonb,
  dependency_direction TEXT NOT NULL DEFAULT 'source_depends_on_target',
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO nexus.relationship_type_catalog(relationship_type,display_name,description,dependency_direction) VALUES
('depends_on','Depends On','Source requires target to operate.','source_depends_on_target'),
('hosted_on','Hosted On','Source workload or service runs on target host.','source_depends_on_target'),
('runs_workload','Runs Workload','Compute asset executes the target workload.','target_depends_on_source'),
('uses_service','Uses Service','Source consumes a service provided by target.','source_depends_on_target'),
('connects_to','Connects To','Source has a network or protocol connection to target.','bidirectional'),
('mines_through','Mines Through','Compute workload submits mining work through target pool.','source_depends_on_target'),
('rented_through','Rented Through','Compute capacity is offered through a rental provider.','source_depends_on_target'),
('powered_by','Powered By','Source receives electrical power from target.','source_depends_on_target'),
('backed_by','Backed By','Source is protected or backed by target.','source_depends_on_target'),
('member_of','Member Of','Source belongs to target group, rack, site, or cluster.','source_depends_on_target')
ON CONFLICT (relationship_type) DO UPDATE SET display_name=EXCLUDED.display_name,description=EXCLUDED.description,dependency_direction=EXCLUDED.dependency_direction;

CREATE TABLE IF NOT EXISTS nexus.relationship_history (
  history_id TEXT PRIMARY KEY,
  relationship_id TEXT NOT NULL,
  action TEXT NOT NULL,
  before_state JSONB NOT NULL DEFAULT '{}'::jsonb,
  after_state JSONB NOT NULL DEFAULT '{}'::jsonb,
  reason TEXT NOT NULL DEFAULT '',
  changed_by TEXT NOT NULL DEFAULT 'nexus',
  source TEXT NOT NULL DEFAULT 'cmdb',
  correlation_id TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_relationship_history_rel ON nexus.relationship_history(relationship_id,created_at DESC);

CREATE TABLE IF NOT EXISTS nexus.compute_capabilities (
  asset_id TEXT PRIMARY KEY REFERENCES nexus.assets(asset_id) ON DELETE CASCADE,
  compute_kind TEXT NOT NULL CHECK (compute_kind IN ('asic','gpu','cpu','fpga','hybrid','general')),
  vendor TEXT NOT NULL DEFAULT '', model TEXT NOT NULL DEFAULT '', device_count INTEGER NOT NULL DEFAULT 1,
  memory_bytes BIGINT, capabilities JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nexus.workload_assignments (
  assignment_id TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL REFERENCES nexus.assets(asset_id) ON DELETE CASCADE,
  workload_category TEXT NOT NULL CHECK (workload_category IN ('mining','ai-inference','ai-training','gpu-rental','cpu-rental','rendering','video-encoding','general-compute')),
  workload_name TEXT NOT NULL,
  target_type TEXT NOT NULL DEFAULT '', target_id TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'assigned', metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), ended_at TIMESTAMPTZ,
  created_by TEXT NOT NULL DEFAULT 'nexus', updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_workload_assignments_asset ON nexus.workload_assignments(asset_id,status);
COMMIT;
