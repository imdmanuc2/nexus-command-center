BEGIN;
CREATE SCHEMA IF NOT EXISTS nexus;
CREATE TABLE IF NOT EXISTS nexus.software_packages (
 package_id text PRIMARY KEY, name text NOT NULL, version text NOT NULL,
 package_type text NOT NULL DEFAULT 'application', source_uri text NOT NULL DEFAULT '',
 checksum_sha256 text NOT NULL DEFAULT '', metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
 created_at timestamptz NOT NULL DEFAULT now(), created_by text NOT NULL DEFAULT 'nexus',
 UNIQUE(name, version)
);
CREATE TABLE IF NOT EXISTS nexus.deployment_jobs (
 job_id text PRIMARY KEY, package_id text REFERENCES nexus.software_packages(package_id),
 name text NOT NULL, deployment_type text NOT NULL DEFAULT 'software', status text NOT NULL DEFAULT 'queued',
 strategy text NOT NULL DEFAULT 'rolling', requested_by text NOT NULL DEFAULT 'nexus',
 requested_at timestamptz NOT NULL DEFAULT now(), started_at timestamptz, completed_at timestamptz,
 approval_id text, correlation_id text NOT NULL, parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
 result jsonb NOT NULL DEFAULT '{}'::jsonb, CONSTRAINT deployment_status_ck CHECK(status IN ('draft','queued','approved','running','succeeded','failed','cancelled','partial'))
);
CREATE TABLE IF NOT EXISTS nexus.deployment_targets (
 target_id bigserial PRIMARY KEY, job_id text NOT NULL REFERENCES nexus.deployment_jobs(job_id) ON DELETE CASCADE,
 target_asset_id text NOT NULL, target_asset_type text NOT NULL DEFAULT 'asset', status text NOT NULL DEFAULT 'queued',
 current_version text NOT NULL DEFAULT '', desired_version text NOT NULL DEFAULT '',
 started_at timestamptz, completed_at timestamptz, result jsonb NOT NULL DEFAULT '{}'::jsonb,
 UNIQUE(job_id,target_asset_id), CONSTRAINT deployment_target_status_ck CHECK(status IN ('queued','running','succeeded','failed','skipped','cancelled'))
);
CREATE INDEX IF NOT EXISTS idx_deployment_jobs_status ON nexus.deployment_jobs(status, requested_at DESC);
CREATE INDEX IF NOT EXISTS idx_deployment_targets_asset ON nexus.deployment_targets(target_asset_id, status);
COMMIT;
