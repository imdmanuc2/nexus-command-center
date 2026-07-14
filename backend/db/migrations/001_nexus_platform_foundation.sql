BEGIN;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  description TEXT NOT NULL,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE SCHEMA IF NOT EXISTS nexus;

CREATE TABLE IF NOT EXISTS nexus.assets (
  asset_id TEXT PRIMARY KEY,
  asset_type TEXT NOT NULL DEFAULT 'unknown',
  canonical_type TEXT NOT NULL DEFAULT 'unknown',
  name TEXT NOT NULL,
  friendly_name TEXT NOT NULL,
  display_name TEXT NOT NULL,
  purpose TEXT NOT NULL DEFAULT '',
  primary_role TEXT NOT NULL DEFAULT '',
  coin TEXT,
  lifecycle_status TEXT NOT NULL DEFAULT 'managed',
  managed BOOLEAN NOT NULL DEFAULT TRUE,
  favorite BOOLEAN NOT NULL DEFAULT FALSE,
  criticality TEXT NOT NULL DEFAULT 'normal',
  owner TEXT NOT NULL DEFAULT '',
  business_service TEXT NOT NULL DEFAULT '',
  location TEXT NOT NULL DEFAULT '',
  rack TEXT NOT NULL DEFAULT '',
  position TEXT NOT NULL DEFAULT '',
  manufacturer TEXT NOT NULL DEFAULT '',
  model TEXT NOT NULL DEFAULT '',
  serial_number TEXT NOT NULL DEFAULT '',
  operating_system TEXT NOT NULL DEFAULT '',
  architecture TEXT NOT NULL DEFAULT '',
  hypervisor TEXT NOT NULL DEFAULT '',
  container_runtime TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  compute_profile JSONB NOT NULL DEFAULT '{}'::JSONB,
  capabilities JSONB NOT NULL DEFAULT '[]'::JSONB,
  allocation JSONB NOT NULL DEFAULT '{}'::JSONB,
  desired_state JSONB NOT NULL DEFAULT '{}'::JSONB,
  observed_state JSONB NOT NULL DEFAULT '{}'::JSONB,
  metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_automatically BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ,
  retired_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_assets_type ON nexus.assets(asset_type);
CREATE INDEX IF NOT EXISTS idx_assets_lifecycle ON nexus.assets(lifecycle_status);
CREATE INDEX IF NOT EXISTS idx_assets_last_seen ON nexus.assets(last_seen_at DESC);

CREATE TABLE IF NOT EXISTS nexus.asset_identities (
  identity_id BIGSERIAL PRIMARY KEY,
  asset_id TEXT NOT NULL REFERENCES nexus.assets(asset_id) ON DELETE CASCADE,
  identity_type TEXT NOT NULL,
  identity_value TEXT NOT NULL,
  normalized_value TEXT NOT NULL,
  confidence NUMERIC(5,2),
  source TEXT NOT NULL DEFAULT 'unknown',
  is_primary BOOLEAN NOT NULL DEFAULT FALSE,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
  UNIQUE(identity_type, normalized_value)
);
CREATE INDEX IF NOT EXISTS idx_asset_identities_asset ON nexus.asset_identities(asset_id);

CREATE TABLE IF NOT EXISTS nexus.asset_network_addresses (
  address_id BIGSERIAL PRIMARY KEY,
  asset_id TEXT NOT NULL REFERENCES nexus.assets(asset_id) ON DELETE CASCADE,
  address_type TEXT NOT NULL DEFAULT 'ipv4',
  address TEXT NOT NULL,
  network_segment TEXT NOT NULL DEFAULT '',
  is_primary BOOLEAN NOT NULL DEFAULT FALSE,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  retired_at TIMESTAMPTZ,
  metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
  UNIQUE(asset_id,address)
);
CREATE INDEX IF NOT EXISTS idx_asset_addresses_address ON nexus.asset_network_addresses(address);

CREATE TABLE IF NOT EXISTS nexus.asset_components (
  component_id TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL REFERENCES nexus.assets(asset_id) ON DELETE CASCADE,
  component_type TEXT NOT NULL,
  name TEXT NOT NULL,
  manufacturer TEXT NOT NULL DEFAULT '',
  model TEXT NOT NULL DEFAULT '',
  serial_number TEXT NOT NULL DEFAULT '',
  hardware_uuid TEXT NOT NULL DEFAULT '',
  pci_address TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'unknown',
  health TEXT NOT NULL DEFAULT 'unknown',
  specifications JSONB NOT NULL DEFAULT '{}'::JSONB,
  observed_state JSONB NOT NULL DEFAULT '{}'::JSONB,
  metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_components_asset ON nexus.asset_components(asset_id);

CREATE TABLE IF NOT EXISTS nexus.workers (
  worker_id TEXT PRIMARY KEY,
  worker_type TEXT NOT NULL DEFAULT 'unknown',
  hardware_type TEXT NOT NULL DEFAULT '',
  display_name TEXT NOT NULL,
  asset_id TEXT REFERENCES nexus.assets(asset_id) ON DELETE SET NULL,
  asset_matched BOOLEAN NOT NULL DEFAULT FALSE,
  reconciliation_status TEXT NOT NULL DEFAULT 'unmatched',
  pool_id TEXT,
  coin TEXT,
  status TEXT NOT NULL DEFAULT 'unknown',
  current_hashrate NUMERIC,
  hashrate_unit TEXT NOT NULL DEFAULT '',
  identity JSONB NOT NULL DEFAULT '{}'::JSONB,
  observed_state JSONB NOT NULL DEFAULT '{}'::JSONB,
  metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_workers_asset ON nexus.workers(asset_id);
CREATE INDEX IF NOT EXISTS idx_workers_pool ON nexus.workers(pool_id);

CREATE TABLE IF NOT EXISTS nexus.workloads (
  workload_id TEXT PRIMARY KEY,
  asset_id TEXT REFERENCES nexus.assets(asset_id) ON DELETE SET NULL,
  worker_id TEXT REFERENCES nexus.workers(worker_id) ON DELETE SET NULL,
  workload_type TEXT NOT NULL,
  name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'unknown',
  runtime TEXT NOT NULL DEFAULT '',
  software TEXT NOT NULL DEFAULT '',
  version TEXT NOT NULL DEFAULT '',
  coin TEXT,
  pool_id TEXT,
  allocation JSONB NOT NULL DEFAULT '{}'::JSONB,
  configuration JSONB NOT NULL DEFAULT '{}'::JSONB,
  observed_state JSONB NOT NULL DEFAULT '{}'::JSONB,
  revenue_state JSONB NOT NULL DEFAULT '{}'::JSONB,
  metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
  started_at TIMESTAMPTZ,
  stopped_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nexus.relationships (
  relationship_id TEXT PRIMARY KEY,
  source_type TEXT NOT NULL DEFAULT 'asset',
  source_id TEXT NOT NULL,
  relationship_type TEXT NOT NULL,
  target_type TEXT NOT NULL DEFAULT 'asset',
  target_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  confidence NUMERIC(5,2),
  source TEXT NOT NULL DEFAULT 'cmdb',
  observed BOOLEAN NOT NULL DEFAULT FALSE,
  approved BOOLEAN NOT NULL DEFAULT TRUE,
  metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(source_type,source_id,relationship_type,target_type,target_id)
);
CREATE INDEX IF NOT EXISTS idx_relationships_source ON nexus.relationships(source_type,source_id);
CREATE INDEX IF NOT EXISTS idx_relationships_target ON nexus.relationships(target_type,target_id);

CREATE TABLE IF NOT EXISTS nexus.discovery_scopes (
  scope_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  cidr TEXT NOT NULL UNIQUE,
  site TEXT NOT NULL DEFAULT '',
  vlan TEXT NOT NULL DEFAULT '',
  purpose TEXT NOT NULL DEFAULT '',
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  scan_schedule TEXT NOT NULL DEFAULT '',
  credential_profile TEXT NOT NULL DEFAULT '',
  last_scan_at TIMESTAMPTZ,
  last_success_at TIMESTAMPTZ,
  metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nexus.discovery_scans (
  scan_id TEXT PRIMARY KEY,
  scope_id TEXT REFERENCES nexus.discovery_scopes(scope_id) ON DELETE SET NULL,
  observer_id TEXT NOT NULL DEFAULT 'nexus',
  status TEXT NOT NULL DEFAULT 'pending',
  targets_requested INTEGER NOT NULL DEFAULT 0,
  targets_scanned INTEGER NOT NULL DEFAULT 0,
  systems_found INTEGER NOT NULL DEFAULT 0,
  correlation_id TEXT NOT NULL,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  summary JSONB NOT NULL DEFAULT '{}'::JSONB,
  metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nexus.observations (
  observation_id TEXT PRIMARY KEY,
  scan_id TEXT REFERENCES nexus.discovery_scans(scan_id) ON DELETE SET NULL,
  observed_at TIMESTAMPTZ NOT NULL,
  received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  source TEXT NOT NULL DEFAULT 'unknown',
  observer_id TEXT NOT NULL DEFAULT 'nexus',
  correlation_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  decision TEXT NOT NULL DEFAULT '',
  matched_asset_id TEXT REFERENCES nexus.assets(asset_id) ON DELETE SET NULL,
  confidence NUMERIC(5,2),
  identity JSONB NOT NULL DEFAULT '{}'::JSONB,
  classification JSONB NOT NULL DEFAULT '{}'::JSONB,
  network JSONB NOT NULL DEFAULT '{}'::JSONB,
  compute JSONB NOT NULL DEFAULT '{}'::JSONB,
  raw_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_observations_status ON nexus.observations(status,received_at DESC);

CREATE TABLE IF NOT EXISTS nexus.reconciliation_cases (
  case_id TEXT PRIMARY KEY,
  observation_id TEXT NOT NULL REFERENCES nexus.observations(observation_id) ON DELETE CASCADE,
  candidate_asset_id TEXT REFERENCES nexus.assets(asset_id) ON DELETE SET NULL,
  case_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  confidence NUMERIC(5,2),
  evidence JSONB NOT NULL DEFAULT '[]'::JSONB,
  conflicts JSONB NOT NULL DEFAULT '[]'::JSONB,
  resolution JSONB NOT NULL DEFAULT '{}'::JSONB,
  assigned_to TEXT NOT NULL DEFAULT '',
  resolved_by TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  resolved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS nexus.pools (
  pool_id TEXT PRIMARY KEY,
  asset_id TEXT REFERENCES nexus.assets(asset_id) ON DELETE SET NULL,
  name TEXT NOT NULL,
  coin TEXT NOT NULL,
  mode TEXT NOT NULL DEFAULT 'solo',
  visibility TEXT NOT NULL DEFAULT 'private',
  status TEXT NOT NULL DEFAULT 'unknown',
  configuration JSONB NOT NULL DEFAULT '{}'::JSONB,
  observed_state JSONB NOT NULL DEFAULT '{}'::JSONB,
  metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS nexus.blockchain_nodes (
  node_id TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL REFERENCES nexus.assets(asset_id) ON DELETE CASCADE,
  coin TEXT NOT NULL,
  network TEXT NOT NULL DEFAULT 'mainnet',
  implementation TEXT NOT NULL DEFAULT '',
  version TEXT NOT NULL DEFAULT '',
  rpc_endpoint JSONB NOT NULL DEFAULT '{}'::JSONB,
  p2p_endpoint JSONB NOT NULL DEFAULT '{}'::JSONB,
  status TEXT NOT NULL DEFAULT 'unknown',
  sync_status TEXT NOT NULL DEFAULT 'unknown',
  block_height BIGINT,
  header_height BIGINT,
  peer_count INTEGER,
  observed_state JSONB NOT NULL DEFAULT '{}'::JSONB,
  metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ,
  UNIQUE(asset_id,coin,network)
);

CREATE TABLE IF NOT EXISTS nexus.tags (
  tag_id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  description TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS nexus.asset_tags (
  asset_id TEXT NOT NULL REFERENCES nexus.assets(asset_id) ON DELETE CASCADE,
  tag_id BIGINT NOT NULL REFERENCES nexus.tags(tag_id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY(asset_id,tag_id)
);

CREATE TABLE IF NOT EXISTS nexus.audit_events (
  event_id TEXT PRIMARY KEY,
  occurred_at TIMESTAMPTZ NOT NULL,
  category TEXT NOT NULL DEFAULT 'cmdb',
  action TEXT NOT NULL,
  asset_id TEXT REFERENCES nexus.assets(asset_id) ON DELETE SET NULL,
  asset_type TEXT NOT NULL DEFAULT '',
  asset_name TEXT NOT NULL DEFAULT '',
  actor_type TEXT NOT NULL DEFAULT 'system',
  actor_id TEXT NOT NULL DEFAULT 'nexus',
  source TEXT NOT NULL DEFAULT 'cmdb',
  reason TEXT NOT NULL DEFAULT '',
  correlation_id TEXT NOT NULL,
  confidence NUMERIC(5,2),
  changes JSONB NOT NULL DEFAULT '[]'::JSONB,
  metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_events_asset ON nexus.audit_events(asset_id,occurred_at DESC);

CREATE TABLE IF NOT EXISTS nexus.events (
  event_id TEXT PRIMARY KEY,
  occurred_at TIMESTAMPTZ NOT NULL,
  event_type TEXT NOT NULL,
  severity TEXT NOT NULL DEFAULT 'info',
  status TEXT NOT NULL DEFAULT 'open',
  subject_type TEXT NOT NULL DEFAULT '',
  subject_id TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL,
  message TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL DEFAULT 'nexus',
  correlation_id TEXT NOT NULL DEFAULT '',
  data JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  resolved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS nexus.alerts (
  alert_id TEXT PRIMARY KEY,
  asset_id TEXT REFERENCES nexus.assets(asset_id) ON DELETE SET NULL,
  event_id TEXT REFERENCES nexus.events(event_id) ON DELETE SET NULL,
  alert_type TEXT NOT NULL,
  severity TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  title TEXT NOT NULL,
  message TEXT NOT NULL DEFAULT '',
  rule_id TEXT NOT NULL DEFAULT '',
  occurrence_count INTEGER NOT NULL DEFAULT 1,
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  acknowledged_at TIMESTAMPTZ,
  acknowledged_by TEXT NOT NULL DEFAULT '',
  resolved_at TIMESTAMPTZ,
  data JSONB NOT NULL DEFAULT '{}'::JSONB
);

CREATE TABLE IF NOT EXISTS nexus.playbooks (
  playbook_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  target_asset_types JSONB NOT NULL DEFAULT '[]'::JSONB,
  definition JSONB NOT NULL DEFAULT '{}'::JSONB,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  version INTEGER NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS nexus.playbook_runs (
  run_id TEXT PRIMARY KEY,
  playbook_id TEXT NOT NULL REFERENCES nexus.playbooks(playbook_id) ON DELETE RESTRICT,
  asset_id TEXT REFERENCES nexus.assets(asset_id) ON DELETE SET NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  triggered_by TEXT NOT NULL DEFAULT 'operator',
  correlation_id TEXT NOT NULL,
  input_data JSONB NOT NULL DEFAULT '{}'::JSONB,
  result_data JSONB NOT NULL DEFAULT '{}'::JSONB,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nexus.automation_rules (
  rule_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  trigger_definition JSONB NOT NULL DEFAULT '{}'::JSONB,
  condition_definition JSONB NOT NULL DEFAULT '{}'::JSONB,
  action_definition JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nexus.telemetry_samples (
  sample_id BIGSERIAL PRIMARY KEY,
  subject_type TEXT NOT NULL,
  subject_id TEXT NOT NULL,
  metric_name TEXT NOT NULL,
  metric_value DOUBLE PRECISION,
  metric_unit TEXT NOT NULL DEFAULT '',
  observed_at TIMESTAMPTZ NOT NULL,
  dimensions JSONB NOT NULL DEFAULT '{}'::JSONB,
  data JSONB NOT NULL DEFAULT '{}'::JSONB
);
CREATE INDEX IF NOT EXISTS idx_telemetry_lookup ON nexus.telemetry_samples(subject_type,subject_id,metric_name,observed_at DESC);

INSERT INTO schema_migrations(version,description)
VALUES ('001','Nexus platform database foundation')
ON CONFLICT(version) DO NOTHING;
COMMIT;
