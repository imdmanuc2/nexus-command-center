
BEGIN;

CREATE SCHEMA IF NOT EXISTS nexus;

ALTER TABLE nexus.workers
    ADD COLUMN IF NOT EXISTS activity_state TEXT NOT NULL DEFAULT 'unknown',
    ADD COLUMN IF NOT EXISTS connection_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS telemetry_available BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS last_hashrate_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_connected_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS current_session BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS retired_at TIMESTAMPTZ;

ALTER TABLE nexus.workers
    DROP CONSTRAINT IF EXISTS workers_activity_state_check;

ALTER TABLE nexus.workers
    ADD CONSTRAINT workers_activity_state_check
    CHECK (
        activity_state IN (
            'active',
            'idle',
            'stale',
            'offline',
            'unknown'
        )
    );

CREATE INDEX IF NOT EXISTS idx_workers_activity_current
ON nexus.workers (
    activity_state,
    current_session,
    asset_id,
    last_seen_at DESC
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_workers_one_current_session_per_asset
ON nexus.workers(asset_id)
WHERE asset_id IS NOT NULL
  AND current_session = TRUE;

CREATE OR REPLACE FUNCTION nexus.normalize_worker_current_metrics()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.activity_state IN ('offline', 'stale', 'unknown') THEN
        NEW.current_hashrate := 0;
        NEW.shares_per_second := 0;
    END IF;

    IF NEW.status IN ('offline', 'stale', 'down', 'error') THEN
        NEW.current_hashrate := 0;
        NEW.shares_per_second := 0;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_workers_normalize_current_metrics
ON nexus.workers;

CREATE TRIGGER trg_workers_normalize_current_metrics
BEFORE INSERT OR UPDATE
ON nexus.workers
FOR EACH ROW
EXECUTE FUNCTION nexus.normalize_worker_current_metrics();

UPDATE nexus.workers
SET
    activity_state = CASE
        WHEN LOWER(COALESCE(status, '')) IN ('offline', 'stale', 'down', 'error')
            THEN 'offline'
        WHEN source_system = 'generic-stratum'
             AND COALESCE(current_hashrate, 0) <= 0
             AND COALESCE(shares_per_second, 0) <= 0
             AND last_share_at IS NULL
            THEN 'unknown'
        WHEN COALESCE(current_hashrate, 0) > 0
             OR COALESCE(shares_per_second, 0) > 0
             OR last_share_at IS NOT NULL
            THEN 'active'
        ELSE 'idle'
    END,
    telemetry_available = (
        COALESCE(current_hashrate, 0) > 0
        OR COALESCE(shares_per_second, 0) > 0
        OR last_share_at IS NOT NULL
    ),
    connection_confirmed = CASE
        WHEN source_system = 'generic-stratum'
             AND COALESCE(current_hashrate, 0) <= 0
             AND COALESCE(shares_per_second, 0) <= 0
             AND last_share_at IS NULL
            THEN FALSE
        ELSE LOWER(COALESCE(status, '')) IN ('online', 'active', 'connected', 'mining')
    END,
    last_hashrate_at = CASE
        WHEN COALESCE(current_hashrate, 0) > 0
            THEN COALESCE(last_hashrate_at, last_seen_at, NOW())
        ELSE last_hashrate_at
    END,
    last_connected_at = CASE
        WHEN LOWER(COALESCE(status, '')) IN ('online', 'active', 'connected', 'mining')
            THEN COALESCE(last_connected_at, last_seen_at, NOW())
        ELSE last_connected_at
    END;

UPDATE nexus.workers
SET
    current_hashrate = 0,
    shares_per_second = 0
WHERE activity_state IN ('offline', 'stale', 'unknown')
   OR LOWER(COALESCE(status, '')) IN ('offline', 'stale', 'down', 'error');

INSERT INTO public.schema_migrations(version, description)
VALUES ('014', 'Worker identity and activity reconciliation')
ON CONFLICT (version) DO NOTHING;

COMMIT;
