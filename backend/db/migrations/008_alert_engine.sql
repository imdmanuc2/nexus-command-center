BEGIN;

CREATE SCHEMA IF NOT EXISTS nexus;

CREATE TABLE IF NOT EXISTS nexus.alert_rules (
    rule_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    entity_type TEXT NOT NULL DEFAULT '*',
    event_type TEXT NOT NULL,
    minimum_severity TEXT NOT NULL DEFAULT 'warning',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    auto_resolve BOOLEAN NOT NULL DEFAULT TRUE,
    cooldown_seconds INTEGER NOT NULL DEFAULT 300,
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nexus.alert_engine_state (
    engine_name TEXT PRIMARY KEY,
    last_event_id BIGINT NOT NULL DEFAULT 0,
    last_started_at TIMESTAMPTZ,
    last_completed_at TIMESTAMPTZ,
    last_status TEXT NOT NULL DEFAULT 'never-run',
    last_error TEXT NOT NULL DEFAULT '',
    evaluated_events INTEGER NOT NULL DEFAULT 0,
    alerts_opened INTEGER NOT NULL DEFAULT 0,
    alerts_updated INTEGER NOT NULL DEFAULT 0,
    alerts_resolved INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_alerts_active_grouping
ON nexus.alerts(grouping_key)
WHERE status IN ('open', 'acknowledged')
  AND grouping_key <> '';

INSERT INTO nexus.alert_rules (
    rule_id,
    name,
    description,
    entity_type,
    event_type,
    minimum_severity,
    enabled,
    auto_resolve,
    cooldown_seconds
)
VALUES
(
    'resource-offline',
    'Resource Offline',
    'Open a critical alert when a persisted resource goes offline.',
    '*',
    'resource.offline',
    'critical',
    TRUE,
    TRUE,
    300
),
(
    'resource-degraded',
    'Resource Degraded',
    'Open a warning alert when a resource enters a degraded state.',
    '*',
    'resource.status_changed',
    'warning',
    TRUE,
    TRUE,
    300
),
(
    'endpoint-changed',
    'Endpoint Changed',
    'Track endpoint changes for persisted services.',
    '*',
    'resource.endpoint_changed',
    'warning',
    TRUE,
    FALSE,
    900
),
(
    'version-changed',
    'Version Changed',
    'Track software version changes.',
    '*',
    'resource.version_changed',
    'info',
    TRUE,
    FALSE,
    900
)
ON CONFLICT (rule_id) DO NOTHING;

INSERT INTO public.schema_migrations (
    version,
    description
)
VALUES (
    '008',
    'Platform alert rules and event-driven alert evaluation'
)
ON CONFLICT (version) DO NOTHING;

COMMIT;
