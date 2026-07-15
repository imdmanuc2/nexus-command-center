BEGIN;

CREATE SCHEMA IF NOT EXISTS nexus;

CREATE TABLE IF NOT EXISTS nexus.platform_context_snapshots (
    context_key TEXT PRIMARY KEY,
    context_version TEXT NOT NULL DEFAULT 'v1',
    context_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_state JSONB NOT NULL DEFAULT '{}'::JSONB,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_platform_context_generated_at
ON nexus.platform_context_snapshots(generated_at DESC);

CREATE TABLE IF NOT EXISTS nexus.ai_context_builder_state (
    builder_name TEXT PRIMARY KEY,
    last_started_at TIMESTAMPTZ,
    last_completed_at TIMESTAMPTZ,
    last_status TEXT NOT NULL DEFAULT 'never-run',
    last_error TEXT NOT NULL DEFAULT '',
    contexts_written INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO public.schema_migrations(version, description)
VALUES ('009', 'Derived Platform AI context snapshots')
ON CONFLICT (version) DO NOTHING;

COMMIT;
