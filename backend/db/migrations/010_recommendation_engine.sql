BEGIN;

CREATE SCHEMA IF NOT EXISTS nexus;

CREATE TABLE IF NOT EXISTS nexus.recommendations (
    recommendation_id TEXT PRIMARY KEY,
    rule_id TEXT NOT NULL,
    category TEXT NOT NULL,
    priority TEXT NOT NULL,
    priority_score INTEGER NOT NULL DEFAULT 50,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    title TEXT NOT NULL,
    explanation TEXT NOT NULL DEFAULT '',
    recommended_action TEXT NOT NULL DEFAULT '',
    evidence JSONB NOT NULL DEFAULT '{}'::JSONB,
    status TEXT NOT NULL DEFAULT 'open',
    first_generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    accepted_at TIMESTAMPTZ,
    dismissed_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    generation_count INTEGER NOT NULL DEFAULT 1,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_recommendations_open_rule_entity
ON nexus.recommendations(rule_id, entity_type, entity_id)
WHERE status IN ('open', 'accepted');

CREATE INDEX IF NOT EXISTS idx_recommendations_priority
ON nexus.recommendations(status, priority_score DESC, last_generated_at DESC);

CREATE INDEX IF NOT EXISTS idx_recommendations_entity
ON nexus.recommendations(entity_type, entity_id, last_generated_at DESC);

CREATE TABLE IF NOT EXISTS nexus.recommendation_engine_state (
    engine_name TEXT PRIMARY KEY,
    last_started_at TIMESTAMPTZ,
    last_completed_at TIMESTAMPTZ,
    last_status TEXT NOT NULL DEFAULT 'never-run',
    last_error TEXT NOT NULL DEFAULT '',
    evaluated_rules INTEGER NOT NULL DEFAULT 0,
    recommendations_opened INTEGER NOT NULL DEFAULT 0,
    recommendations_updated INTEGER NOT NULL DEFAULT 0,
    recommendations_resolved INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO public.schema_migrations(version, description)
VALUES ('010', 'Platform recommendation engine')
ON CONFLICT (version) DO NOTHING;

COMMIT;
