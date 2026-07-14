BEGIN;

 

-- ============================================================

-- WORKERS: POOL INSTANCE IDENTITY

-- ============================================================

 

ALTER TABLE nexus.workers

    ADD COLUMN IF NOT EXISTS pool_instance_id TEXT,

    ADD COLUMN IF NOT EXISTS native_pool_id TEXT,

    ADD COLUMN IF NOT EXISTS pool_host TEXT NOT NULL DEFAULT '',

    ADD COLUMN IF NOT EXISTS pool_api_port INTEGER,

    ADD COLUMN IF NOT EXISTS worker_name TEXT NOT NULL DEFAULT '',

    ADD COLUMN IF NOT EXISTS miner_address TEXT NOT NULL DEFAULT '';

 

CREATE INDEX IF NOT EXISTS idx_workers_pool_instance

    ON nexus.workers(pool_instance_id);

 

CREATE INDEX IF NOT EXISTS idx_workers_pool_host_native

    ON nexus.workers(pool_host, native_pool_id);

 

-- ============================================================

-- WORKERS: LIVE MINING METRICS AND SOURCE IDENTITY

-- ============================================================

 

ALTER TABLE nexus.workers

    ADD COLUMN IF NOT EXISTS shares_per_second NUMERIC,

    ADD COLUMN IF NOT EXISTS accepted_shares NUMERIC,

    ADD COLUMN IF NOT EXISTS rejected_shares NUMERIC,

    ADD COLUMN IF NOT EXISTS last_share_at TIMESTAMPTZ,

    ADD COLUMN IF NOT EXISTS source_system TEXT NOT NULL DEFAULT '',

    ADD COLUMN IF NOT EXISTS source_worker_id TEXT NOT NULL DEFAULT '';

 

CREATE UNIQUE INDEX IF NOT EXISTS uq_workers_source_identity

    ON nexus.workers(source_system, source_worker_id)

    WHERE source_system <> '' AND source_worker_id <> '';

 

CREATE INDEX IF NOT EXISTS idx_workers_last_share

    ON nexus.workers(last_share_at DESC);

 

-- ============================================================

-- WORKERS: CLASSIFICATION METADATA

-- ============================================================

 

ALTER TABLE nexus.workers

    ADD COLUMN IF NOT EXISTS classification_source TEXT NOT NULL DEFAULT '',

    ADD COLUMN IF NOT EXISTS classification_confidence NUMERIC(5,2);

 

COMMENT ON COLUMN nexus.workers.worker_type IS

    'Recommended values: asic, cpu, gpu, fpga, external, unknown';

 

COMMENT ON COLUMN nexus.workers.hardware_type IS

    'Recommended values: ASIC, CPU, GPU, FPGA, Virtual, Unknown';

 

COMMENT ON COLUMN nexus.workers.classification_source IS

    'How Nexus classified the worker, such as MiningCore agent, CMDB match, operator, or heuristic';

 

COMMENT ON COLUMN nexus.workers.classification_confidence IS

    'Classification confidence from 0.00 through 100.00';

 

-- ============================================================

-- POOLS: STABLE INSTANCE IDENTITY

-- ============================================================

 

ALTER TABLE nexus.pools

    ADD COLUMN IF NOT EXISTS native_pool_id TEXT NOT NULL DEFAULT '',

    ADD COLUMN IF NOT EXISTS instance_name TEXT NOT NULL DEFAULT '',

    ADD COLUMN IF NOT EXISTS host TEXT NOT NULL DEFAULT '',

    ADD COLUMN IF NOT EXISTS api_port INTEGER,

    ADD COLUMN IF NOT EXISTS api_base TEXT NOT NULL DEFAULT '',

    ADD COLUMN IF NOT EXISTS stratum_ports JSONB NOT NULL DEFAULT '[]'::JSONB;

 

CREATE UNIQUE INDEX IF NOT EXISTS uq_pools_instance_native

    ON nexus.pools(host, api_port, native_pool_id)

    WHERE host <> '' AND native_pool_id <> '';

 

CREATE INDEX IF NOT EXISTS idx_pools_native_pool_id

    ON nexus.pools(native_pool_id);

 

CREATE INDEX IF NOT EXISTS idx_pools_host_api

    ON nexus.pools(host, api_port);

 

-- ============================================================

-- WORKERS: OPTIONAL FOREIGN KEY TO THE UNIQUE POOL INSTANCE

-- ============================================================

-- pool_instance_id is intentionally nullable because workers may be

-- discovered before the pool is inserted or may belong to an external pool.

 

DO $$

BEGIN

    IF NOT EXISTS (

        SELECT 1

        FROM pg_constraint

        WHERE conname = 'fk_workers_pool_instance'

    ) THEN

        ALTER TABLE nexus.workers

            ADD CONSTRAINT fk_workers_pool_instance

            FOREIGN KEY (pool_instance_id)

            REFERENCES nexus.pools(pool_id)

            ON DELETE SET NULL;

    END IF;

END

$$;

 

-- ============================================================

-- PLAYBOOK RUNS: GENERIC TARGETS AND OPERATION METADATA

-- ============================================================

 

ALTER TABLE nexus.playbook_runs

    ADD COLUMN IF NOT EXISTS target_type TEXT NOT NULL DEFAULT 'asset',

    ADD COLUMN IF NOT EXISTS target_id TEXT NOT NULL DEFAULT '',

    ADD COLUMN IF NOT EXISTS action_name TEXT NOT NULL DEFAULT '',

    ADD COLUMN IF NOT EXISTS read_only BOOLEAN NOT NULL DEFAULT TRUE,

    ADD COLUMN IF NOT EXISTS confirmation_required BOOLEAN NOT NULL DEFAULT FALSE,

    ADD COLUMN IF NOT EXISTS duration_ms INTEGER,

    ADD COLUMN IF NOT EXISTS summary TEXT NOT NULL DEFAULT '';

 

CREATE INDEX IF NOT EXISTS idx_playbook_runs_target

    ON nexus.playbook_runs(target_type, target_id, created_at DESC);

 

CREATE INDEX IF NOT EXISTS idx_playbook_runs_action

    ON nexus.playbook_runs(action_name, created_at DESC);

 

CREATE INDEX IF NOT EXISTS idx_playbook_runs_correlation

    ON nexus.playbook_runs(correlation_id, created_at DESC);

 

COMMENT ON COLUMN nexus.playbook_runs.target_type IS

    'Examples: asset, blockchain-node, pool, worker, server, service';

 

COMMENT ON COLUMN nexus.playbook_runs.target_id IS

    'Canonical Nexus identifier for the selected target';

 

COMMENT ON COLUMN nexus.playbook_runs.action_name IS

    'Shared operation name, for example bitcoin.rpc.test or miningcore.pool.readiness';

 

-- ============================================================

-- PLAYBOOK RUN STEPS

-- ============================================================

 

CREATE TABLE IF NOT EXISTS nexus.playbook_run_steps (

    step_id          BIGSERIAL PRIMARY KEY,

    run_id           TEXT NOT NULL

                     REFERENCES nexus.playbook_runs(run_id)

                     ON DELETE CASCADE,

 

    step_order       INTEGER NOT NULL,

    step_key         TEXT NOT NULL DEFAULT '',

    name             TEXT NOT NULL,

    status           TEXT NOT NULL DEFAULT 'unknown',

    summary          TEXT NOT NULL DEFAULT '',

    duration_ms      INTEGER NOT NULL DEFAULT 0,

    required         BOOLEAN NOT NULL DEFAULT FALSE,

    details          JSONB NOT NULL DEFAULT '{}'::JSONB,

 

    started_at       TIMESTAMPTZ,

    completed_at     TIMESTAMPTZ,

    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

 

    UNIQUE(run_id, step_order)

);

 

CREATE INDEX IF NOT EXISTS idx_playbook_steps_run

    ON nexus.playbook_run_steps(run_id, step_order);

 

CREATE INDEX IF NOT EXISTS idx_playbook_steps_status

    ON nexus.playbook_run_steps(status, created_at DESC);

 

CREATE INDEX IF NOT EXISTS idx_playbook_steps_key

    ON nexus.playbook_run_steps(step_key, created_at DESC);

 

-- ============================================================

-- OPTIONAL WORKER OBSERVATION HISTORY

-- ============================================================

 

CREATE TABLE IF NOT EXISTS nexus.worker_observations (

    observation_id     BIGSERIAL PRIMARY KEY,

 

    worker_id          TEXT NOT NULL

                       REFERENCES nexus.workers(worker_id)

                       ON DELETE CASCADE,

 

    pool_instance_id   TEXT

                       REFERENCES nexus.pools(pool_id)

                       ON DELETE SET NULL,

 

    status             TEXT NOT NULL DEFAULT 'unknown',

    hashrate           NUMERIC,

    hashrate_unit      TEXT NOT NULL DEFAULT '',

    shares_per_second  NUMERIC,

    accepted_shares    NUMERIC,

    rejected_shares    NUMERIC,

 

    observed_at        TIMESTAMPTZ NOT NULL,

    data               JSONB NOT NULL DEFAULT '{}'::JSONB,

 

    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()

);

 

CREATE INDEX IF NOT EXISTS idx_worker_observations_worker_time

    ON nexus.worker_observations(worker_id, observed_at DESC);

 

CREATE INDEX IF NOT EXISTS idx_worker_observations_pool_time

    ON nexus.worker_observations(pool_instance_id, observed_at DESC);

 

CREATE INDEX IF NOT EXISTS idx_worker_observations_time

    ON nexus.worker_observations(observed_at DESC);

 

-- ============================================================

-- MIGRATION RECORD

-- ============================================================

 

INSERT INTO schema_migrations (

    version,

    description

)

VALUES (

    '002',

    'Worker pool instances, mining metrics, generic playbook targets, and run steps'

)

ON CONFLICT (version) DO NOTHING;

 

COMMIT;
