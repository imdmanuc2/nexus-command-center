BEGIN;
CREATE TABLE IF NOT EXISTS nexus.engineering_knowledge (
  knowledge_id TEXT PRIMARY KEY,
  asset_type TEXT NOT NULL,
  issue_code TEXT NOT NULL,
  title TEXT NOT NULL,
  symptoms JSONB NOT NULL DEFAULT '[]'::jsonb,
  probable_causes JSONB NOT NULL DEFAULT '[]'::jsonb,
  diagnostic_steps JSONB NOT NULL DEFAULT '[]'::jsonb,
  recommended_actions JSONB NOT NULL DEFAULT '[]'::jsonb,
  playbooks JSONB NOT NULL DEFAULT '[]'::jsonb,
  documentation JSONB NOT NULL DEFAULT '[]'::jsonb,
  base_confidence NUMERIC(5,2) NOT NULL DEFAULT 70,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(asset_type, issue_code)
);
CREATE TABLE IF NOT EXISTS nexus.dependency_analyses (
  analysis_id TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL,
  analysis_type TEXT NOT NULL,
  root_cause_asset_id TEXT,
  root_cause_issue_code TEXT,
  confidence NUMERIC(5,2),
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  dependency_path JSONB NOT NULL DEFAULT '[]'::jsonb,
  impacted_assets JSONB NOT NULL DEFAULT '[]'::jsonb,
  recommendations JSONB NOT NULL DEFAULT '[]'::jsonb,
  status TEXT NOT NULL DEFAULT 'open',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  resolved_at TIMESTAMPTZ,
  resolution_notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_dependency_analyses_asset_created ON nexus.dependency_analyses(asset_id, created_at DESC);
CREATE TABLE IF NOT EXISTS nexus.incident_resolution_outcomes (
  outcome_id TEXT PRIMARY KEY,
  analysis_id TEXT REFERENCES nexus.dependency_analyses(analysis_id) ON DELETE SET NULL,
  asset_id TEXT NOT NULL,
  issue_code TEXT NOT NULL,
  recommendation_code TEXT,
  action_taken TEXT,
  successful BOOLEAN,
  resolution_seconds INTEGER,
  operator_notes TEXT,
  recorded_by TEXT NOT NULL DEFAULT 'nexus-user',
  recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
INSERT INTO nexus.engineering_knowledge(knowledge_id,asset_type,issue_code,title,symptoms,probable_causes,diagnostic_steps,recommended_actions,playbooks,documentation,base_confidence) VALUES
('kb-bitcoin-rpc','blockchain-node','rpc-unavailable','Bitcoin RPC unavailable','["RPC timeout","Connection refused","HTTP error"]','["Bitcoin service stopped","RPC configuration invalid","Firewall or routing failure","Node overloaded or still starting"]','["Check bitcoin service status","Test TCP port 8332","Run authenticated RPC test","Verify rpcbind and rpcallowip","Review node logs","Check sync and disk utilization"]','[{"code":"bitcoin.rpc.test","label":"Test RPC","priority":1},{"code":"bitcoin.service.restart","label":"Restart Bitcoin Service","priority":2},{"code":"logs.view","label":"View Node Logs","priority":3}]','["bitcoin.rpc.test","bitcoin.service.restart"]','["Bitcoin Core RPC Guide"]',92),
('kb-pool-api','pool-engine','api-unavailable','Pool engine API unavailable','["API timeout","Health endpoint failed","Connection refused"]','["Pool service stopped","Database unavailable","Port blocked","Host unavailable"]','["Check pool service status","Test health endpoint","Verify database connectivity","Review application logs","Trace upstream host and network dependencies"]','[{"code":"pool.health.test","label":"Test Pool Health","priority":1},{"code":"service.restart","label":"Restart Pool Service","priority":2},{"code":"logs.view","label":"View Pool Logs","priority":3}]','["miningcore.pool.readiness"]','["Pool Engine Recovery Guide"]',88),
('kb-compute-offline','compute','asset-offline','Compute asset offline','["No heartbeat","No telemetry","Workload unavailable"]','["Power loss","Network path failure","Operating system stopped","Agent or miner process failed"]','["Verify power","Ping management address","Trace switch and host dependencies","Check workload process","Review recent maintenance and deployment history"]','[{"code":"connectivity.test","label":"Test Connectivity","priority":1},{"code":"diagnostics.run","label":"Run Diagnostics","priority":2},{"code":"console.open","label":"Open Console","priority":3}]','["server.connectivity","asic.diagnostics"]','["Compute Asset Recovery Guide"]',80),
('kb-gpu-unavailable','gpu','gpu-unavailable','GPU unavailable','["GPU missing","Driver error","CUDA unavailable","Workload cannot allocate GPU"]','["NVIDIA driver failure","GPU reset required","PCIe or power issue","VRAM exhaustion","Container runtime mismatch"]','["Run nvidia-smi","Check driver and kernel logs","Check power and temperature","Inspect GPU workload allocation","Verify CUDA/container runtime versions"]','[{"code":"gpu.diagnostics","label":"Run GPU Diagnostics","priority":1},{"code":"workload.stop","label":"Stop GPU Workload","priority":2},{"code":"host.reboot","label":"Reboot Host","priority":3}]','["gpu.diagnostics"]','["GPU Operations Guide"]',86)
ON CONFLICT(asset_type,issue_code) DO UPDATE SET title=EXCLUDED.title,symptoms=EXCLUDED.symptoms,probable_causes=EXCLUDED.probable_causes,diagnostic_steps=EXCLUDED.diagnostic_steps,recommended_actions=EXCLUDED.recommended_actions,playbooks=EXCLUDED.playbooks,documentation=EXCLUDED.documentation,base_confidence=EXCLUDED.base_confidence,updated_at=NOW();
COMMIT;
