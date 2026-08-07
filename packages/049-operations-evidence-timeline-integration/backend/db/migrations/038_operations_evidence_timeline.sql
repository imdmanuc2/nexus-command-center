BEGIN;

CREATE TABLE IF NOT EXISTS operation_evidence (
    evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    correlation_id TEXT,
    change_request_id TEXT,
    asset_id TEXT,
    service_id TEXT,
    operation_type TEXT NOT NULL,
    operation_name TEXT NOT NULL,
    actor_type TEXT NOT NULL DEFAULT 'system',
    actor_id TEXT,
    status TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'info',
    summary TEXT NOT NULL,
    score NUMERIC(6,2),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    first_observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(source_type, source_id)
);

CREATE TABLE IF NOT EXISTS operation_evidence_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evidence_id UUID REFERENCES operation_evidence(evidence_id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    status TEXT,
    message TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS operation_annotations (
    annotation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evidence_id UUID REFERENCES operation_evidence(evidence_id) ON DELETE CASCADE,
    asset_id TEXT,
    annotation_type TEXT NOT NULL DEFAULT 'operator-note',
    body TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT 'operator',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS operation_evidence_worker_state (
    worker_name TEXT PRIMARY KEY,
    last_started_at TIMESTAMPTZ,
    last_completed_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    last_error_at TIMESTAMPTZ,
    last_error TEXT,
    last_result JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_operation_evidence_asset ON operation_evidence(asset_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_operation_evidence_correlation ON operation_evidence(correlation_id);
CREATE INDEX IF NOT EXISTS idx_operation_evidence_status ON operation_evidence(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_operation_evidence_type ON operation_evidence(operation_type, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_operation_evidence_events_evidence ON operation_evidence_events(evidence_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_operation_annotations_evidence ON operation_annotations(evidence_id, created_at DESC);

INSERT INTO operation_evidence_worker_state(worker_name)
VALUES ('nexus-operation-evidence-worker')
ON CONFLICT (worker_name) DO NOTHING;

COMMIT;
