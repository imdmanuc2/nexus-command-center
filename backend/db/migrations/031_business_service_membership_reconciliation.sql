BEGIN;

ALTER TABLE nexus.business_service_members
  ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS manually_managed BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS reconciliation_key TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS last_reconciled_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_business_service_members_active
  ON nexus.business_service_members(service_id, active);
CREATE INDEX IF NOT EXISTS idx_business_service_members_reconciliation
  ON nexus.business_service_members(reconciliation_key)
  WHERE reconciliation_key <> '';

CREATE TABLE IF NOT EXISTS nexus.business_service_membership_rules (
  rule_id TEXT PRIMARY KEY,
  service_id TEXT NOT NULL REFERENCES nexus.business_services(service_id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  priority INTEGER NOT NULL DEFAULT 100,
  role TEXT NOT NULL DEFAULT 'component',
  required BOOLEAN NOT NULL DEFAULT FALSE,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  match_definition JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL DEFAULT 'nexus',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_business_service_membership_rules_service
  ON nexus.business_service_membership_rules(service_id, enabled, priority);

CREATE TABLE IF NOT EXISTS nexus.business_service_reconciliation_runs (
  run_id TEXT PRIMARY KEY,
  status TEXT NOT NULL CHECK (status IN ('running','completed','failed')),
  trigger_source TEXT NOT NULL DEFAULT 'manual',
  assets_evaluated INTEGER NOT NULL DEFAULT 0,
  memberships_matched INTEGER NOT NULL DEFAULT 0,
  memberships_created INTEGER NOT NULL DEFAULT 0,
  memberships_updated INTEGER NOT NULL DEFAULT 0,
  memberships_retired INTEGER NOT NULL DEFAULT 0,
  summary JSONB NOT NULL DEFAULT '{}'::jsonb,
  error TEXT NOT NULL DEFAULT '',
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_business_service_reconciliation_runs_started
  ON nexus.business_service_reconciliation_runs(started_at DESC);

INSERT INTO nexus.business_service_membership_rules
(rule_id, service_id, name, description, priority, role, required, match_definition)
VALUES
('rule-bitcoin-workload','svc-bitcoin-mining','Active mining workload','Assets with an active mining workload assignment.',10,'workload-host',TRUE,'{"workloadCategories":["mining"]}'::jsonb),
('rule-bitcoin-coin','svc-bitcoin-mining','Bitcoin coin identity','Assets explicitly classified for BTC or Bitcoin.',20,'bitcoin-component',TRUE,'{"coins":["btc","bitcoin"]}'::jsonb),
('rule-bitcoin-types','svc-bitcoin-mining','Mining infrastructure types','ASICs, miners, Bitcoin nodes, pools, Stratum, and pool-engine components.',30,'mining-component',FALSE,'{"textTerms":["asic","miner","mining","bitcoin","btc","blockchain-node","bitcoin-node","pool","stratum","miningcore","seymour pool engine"]}'::jsonb),
('rule-ai-workload','svc-ai-compute','Active AI workload','Assets assigned to AI inference or training.',10,'ai-workload-host',TRUE,'{"workloadCategories":["ai-inference","ai-training"]}'::jsonb),
('rule-ai-types','svc-ai-compute','AI infrastructure identity','Assets explicitly identified as AI compute or AI workers.',30,'ai-component',FALSE,'{"textTerms":["ai compute","ai-compute","ai worker","inference","training"]}'::jsonb),
('rule-rental-workload','svc-rentable-compute','Active rental workload','Assets assigned to GPU or CPU rental.',10,'rental-worker',TRUE,'{"workloadCategories":["gpu-rental","cpu-rental"]}'::jsonb),
('rule-rental-types','svc-rentable-compute','Rental infrastructure identity','Assets explicitly identified as rental or rentable compute.',30,'rental-component',FALSE,'{"textTerms":["rentable","rental","compute rental","gpu rental","cpu rental"]}'::jsonb)
ON CONFLICT(rule_id) DO UPDATE SET
  service_id=EXCLUDED.service_id,
  name=EXCLUDED.name,
  description=EXCLUDED.description,
  priority=EXCLUDED.priority,
  role=EXCLUDED.role,
  required=EXCLUDED.required,
  match_definition=EXCLUDED.match_definition,
  updated_at=NOW();

COMMIT;
