BEGIN;
CREATE SCHEMA IF NOT EXISTS nexus;
CREATE TABLE IF NOT EXISTS nexus.identity_reconciliation_audit (
 audit_id BIGSERIAL PRIMARY KEY,
 entity_type TEXT NOT NULL,
 canonical_key TEXT NOT NULL,
 canonical_id TEXT NOT NULL,
 incoming_id TEXT NOT NULL DEFAULT '',
 source_system TEXT NOT NULL DEFAULT '',
 source_identity TEXT NOT NULL DEFAULT '',
 action TEXT NOT NULL,
 details JSONB NOT NULL DEFAULT '{}'::JSONB,
 occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_identity_reconciliation_entity
ON nexus.identity_reconciliation_audit(entity_type,canonical_key,occurred_at DESC);
INSERT INTO public.schema_migrations(version,description)
VALUES('013','Natural-key identity reconciliation')
ON CONFLICT(version) DO NOTHING;
COMMIT;
