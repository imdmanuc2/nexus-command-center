BEGIN;
CREATE SCHEMA IF NOT EXISTS nexus;

CREATE TABLE IF NOT EXISTS nexus.sites (
 site_id TEXT PRIMARY KEY,
 name TEXT NOT NULL,
 site_type TEXT NOT NULL DEFAULT 'home',
 status TEXT NOT NULL DEFAULT 'active',
 timezone TEXT NOT NULL DEFAULT 'UTC',
 country TEXT NOT NULL DEFAULT '',
 region TEXT NOT NULL DEFAULT '',
 city TEXT NOT NULL DEFAULT '',
 capacity_power_watts NUMERIC,
 capacity_miners INTEGER,
 metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE nexus.assets ADD COLUMN IF NOT EXISTS site_id TEXT REFERENCES nexus.sites(site_id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_assets_site ON nexus.assets(site_id);

CREATE TABLE IF NOT EXISTS nexus.miningcore_instances (
 instance_id TEXT PRIMARY KEY,
 asset_id TEXT REFERENCES nexus.assets(asset_id) ON DELETE SET NULL,
 site_id TEXT REFERENCES nexus.sites(site_id) ON DELETE SET NULL,
 name TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'unknown',
 environment TEXT NOT NULL DEFAULT 'production',
 api_base_url TEXT NOT NULL,
 console_url TEXT NOT NULL DEFAULT '',
 software_version TEXT NOT NULL DEFAULT '',
 health_score NUMERIC(5,2),
 api_online BOOLEAN NOT NULL DEFAULT FALSE,
 api_latency_ms DOUBLE PRECISION,
 console_online BOOLEAN NOT NULL DEFAULT FALSE,
 process_uptime_sec BIGINT,
 restart_count INTEGER NOT NULL DEFAULT 0,
 license_status TEXT NOT NULL DEFAULT 'unknown',
 developer_fee_status TEXT NOT NULL DEFAULT 'unknown',
 observed_state JSONB NOT NULL DEFAULT '{}'::JSONB,
 metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 last_seen_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_miningcore_status ON nexus.miningcore_instances(status);
CREATE INDEX IF NOT EXISTS idx_miningcore_site ON nexus.miningcore_instances(site_id);
ALTER TABLE nexus.pools ADD COLUMN IF NOT EXISTS instance_id TEXT REFERENCES nexus.miningcore_instances(instance_id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_pools_instance ON nexus.pools(instance_id);

CREATE TABLE IF NOT EXISTS nexus.service_endpoints (
 endpoint_id TEXT PRIMARY KEY,
 subject_type TEXT NOT NULL,
 subject_id TEXT NOT NULL,
 service_type TEXT NOT NULL,
 protocol TEXT NOT NULL DEFAULT 'tcp',
 host TEXT NOT NULL,
 port INTEGER,
 path TEXT NOT NULL DEFAULT '',
 tls_enabled BOOLEAN NOT NULL DEFAULT FALSE,
 status TEXT NOT NULL DEFAULT 'unknown',
 latency_ms DOUBLE PRECISION,
 last_checked_at TIMESTAMPTZ,
 last_healthy_at TIMESTAMPTZ,
 metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
 UNIQUE(subject_type,subject_id,service_type,host,port,path)
);
CREATE INDEX IF NOT EXISTS idx_service_endpoints_subject ON nexus.service_endpoints(subject_type,subject_id);
CREATE INDEX IF NOT EXISTS idx_service_endpoints_health ON nexus.service_endpoints(status,service_type);

CREATE TABLE IF NOT EXISTS nexus.current_metrics (
 subject_type TEXT NOT NULL,
 subject_id TEXT NOT NULL,
 metric_name TEXT NOT NULL,
 metric_value DOUBLE PRECISION,
 metric_unit TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'unknown',
 observed_at TIMESTAMPTZ NOT NULL,
 dimensions JSONB NOT NULL DEFAULT '{}'::JSONB,
 data JSONB NOT NULL DEFAULT '{}'::JSONB,
 PRIMARY KEY(subject_type,subject_id,metric_name)
);
CREATE INDEX IF NOT EXISTS idx_current_metrics_status ON nexus.current_metrics(status,metric_name);
CREATE INDEX IF NOT EXISTS idx_current_metrics_observed ON nexus.current_metrics(observed_at DESC);

CREATE TABLE IF NOT EXISTS nexus.telemetry_rollups (
 bucket_start TIMESTAMPTZ NOT NULL,
 bucket_interval TEXT NOT NULL,
 subject_type TEXT NOT NULL,
 subject_id TEXT NOT NULL,
 metric_name TEXT NOT NULL,
 sample_count INTEGER NOT NULL,
 minimum_value DOUBLE PRECISION,
 maximum_value DOUBLE PRECISION,
 average_value DOUBLE PRECISION,
 first_value DOUBLE PRECISION,
 last_value DOUBLE PRECISION,
 standard_deviation DOUBLE PRECISION,
 dimensions JSONB NOT NULL DEFAULT '{}'::JSONB,
 PRIMARY KEY(bucket_start,bucket_interval,subject_type,subject_id,metric_name)
);
CREATE INDEX IF NOT EXISTS idx_rollups_lookup ON nexus.telemetry_rollups(subject_type,subject_id,metric_name,bucket_interval,bucket_start DESC);

ALTER TABLE nexus.alerts
 ADD COLUMN IF NOT EXISTS priority INTEGER NOT NULL DEFAULT 50,
 ADD COLUMN IF NOT EXISTS actionable BOOLEAN NOT NULL DEFAULT TRUE,
 ADD COLUMN IF NOT EXISTS grouping_key TEXT NOT NULL DEFAULT '',
 ADD COLUMN IF NOT EXISTS parent_alert_id TEXT,
 ADD COLUMN IF NOT EXISTS condition_started_at TIMESTAMPTZ,
 ADD COLUMN IF NOT EXISTS required_duration_sec INTEGER NOT NULL DEFAULT 0,
 ADD COLUMN IF NOT EXISTS suppressed_until TIMESTAMPTZ,
 ADD COLUMN IF NOT EXISTS recommended_action TEXT NOT NULL DEFAULT '',
 ADD COLUMN IF NOT EXISTS playbook_id TEXT;
CREATE INDEX IF NOT EXISTS idx_alerts_priority_queue ON nexus.alerts(status,actionable,priority DESC,last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_grouping ON nexus.alerts(grouping_key) WHERE grouping_key <> '';

CREATE TABLE IF NOT EXISTS nexus.metric_baselines (
 baseline_id BIGSERIAL PRIMARY KEY,
 subject_type TEXT NOT NULL,
 subject_id TEXT NOT NULL,
 metric_name TEXT NOT NULL,
 baseline_type TEXT NOT NULL DEFAULT 'rolling',
 window_seconds INTEGER NOT NULL,
 expected_value DOUBLE PRECISION,
 lower_bound DOUBLE PRECISION,
 upper_bound DOUBLE PRECISION,
 standard_deviation DOUBLE PRECISION,
 sample_count INTEGER NOT NULL DEFAULT 0,
 calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
 UNIQUE(subject_type,subject_id,metric_name,baseline_type,window_seconds)
);

ALTER TABLE nexus.workloads
 ADD COLUMN IF NOT EXISTS pool_instance_id TEXT,
 ADD COLUMN IF NOT EXISTS native_pool_id TEXT NOT NULL DEFAULT '';
DO $$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_workloads_pool_instance') THEN
  ALTER TABLE nexus.workloads ADD CONSTRAINT fk_workloads_pool_instance FOREIGN KEY(pool_instance_id) REFERENCES nexus.pools(pool_id) ON DELETE SET NULL;
 END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_workloads_pool_instance ON nexus.workloads(pool_instance_id);

INSERT INTO schema_migrations(version,description)
VALUES ('003','Home operations, MiningCore instances, current metrics, rollups, baselines, and enterprise alerts')
ON CONFLICT(version) DO NOTHING;
COMMIT;
